#  SPDX-License-Identifier: GPL-3.0-or-later

import os
import hashlib
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QProgressBar,
    QTextEdit,
    QCheckBox,
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt


SALT_FILE_SUFFIX = ".salt"
ENC_FILE_SUFFIX = ".enc"

class EncryptionWorker(QThread):
    """Worker thread for encryption/decryption operations."""
    
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, operation, file_path, password, is_folder=False):
        super().__init__()
        self.operation = operation  # 'encrypt' or 'decrypt'
        self.file_path = file_path
        self.password = password
        self.is_folder = is_folder
        
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        password_bytes = password.encode('utf-8')
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
        return key
    
    def _encrypt_file(self, file_path: str, key: bytes) -> bool:
        """Encrypt a single file."""
        try:
            with open(file_path, 'rb') as file:
                file_data = file.read()
            
            fernet = Fernet(key)
            encrypted_data = fernet.encrypt(file_data)
            
            # Write encrypted data to .enc file
            encrypted_file_path = file_path + ENC_FILE_SUFFIX
            with open(encrypted_file_path, 'wb') as file:
                file.write(encrypted_data)
            
            # Remove original file
            os.remove(file_path)
            return True
        except Exception as e:
            self.status_updated.emit(f"Error encrypting {file_path}: {str(e)}")
            return False
    
    def _decrypt_file(self, file_path: str, key: bytes) -> bool:
        """Decrypt a single file."""
        try:
            with open(file_path, 'rb') as file:
                encrypted_data = file.read()
            
            fernet = Fernet(key)
            decrypted_data = fernet.decrypt(encrypted_data)
            
            # Write decrypted data to original file (remove .enc extension)
            original_file_path = file_path[:-len(ENC_FILE_SUFFIX)]  # Remove .enc extension
            with open(original_file_path, 'wb') as file:
                file.write(decrypted_data)
            
            # Remove encrypted file
            os.remove(file_path)
            return True
        except Exception as e:
            self.status_updated.emit(f"Error decrypting {file_path}: {str(e)}")
            return False
    
    def _get_all_files(self, path: str, operation: str):
        """Get all files to process."""
        files = []
        if os.path.isfile(path):
            if operation == 'encrypt' or (operation == 'decrypt' and path.endswith(ENC_FILE_SUFFIX)):
                files.append(path)
        else:
            # It's a directory
            for root, dirs, filenames in os.walk(path):
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    if (operation == 'encrypt' and not filename.endswith(ENC_FILE_SUFFIX)) or \
                       (operation == 'decrypt' and filename.endswith(ENC_FILE_SUFFIX)):
                        files.append(file_path)
        return files
    
    def run(self):
        """Run the encryption/decryption operation."""
        try:
            # Generate salt
            salt = os.urandom(16)
            key = self._derive_key(self.password, salt)
            
            # Get all files to process
            files_to_process = self._get_all_files(self.file_path, self.operation)
            
            if not files_to_process:
                if self.operation == 'encrypt':
                    message = "No files found to encrypt."
                else:
                    message = "No encrypted files (.enc) found to decrypt."
                self.finished_signal.emit(False, message)
                return
            
            total_files = len(files_to_process)
            successful_operations = 0
            
            # Store salt in a .salt file for the entire operation
            if self.operation == 'encrypt':
                if self.is_folder:
                    salt_file = os.path.join(self.file_path, '.encryption_salt')
                else:
                    # For single files, store salt next to the original file location
                    salt_file = self.file_path + SALT_FILE_SUFFIX
                with open(salt_file, 'wb') as f:
                    f.write(salt)
            else:  # decrypt
                # Read salt
                if self.is_folder:
                    salt_file = os.path.join(self.file_path, '.encryption_salt')
                else:
                    # For single files, the salt file should be next to the original file
                    # If we're decrypting /path/file.txt.enc, salt should be at /path/file.txt.salt
                    if self.file_path.endswith(ENC_FILE_SUFFIX):
                        original_file_path = self.file_path[:-len(ENC_FILE_SUFFIX)]  # Remove .enc
                        salt_file = original_file_path + SALT_FILE_SUFFIX
                    else:
                        salt_file = self.file_path + SALT_FILE_SUFFIX
                
                if os.path.exists(salt_file):
                    with open(salt_file, 'rb') as f:
                        salt = f.read()
                    key = self._derive_key(self.password, salt)
                else:
                    self.finished_signal.emit(False, "Salt file not found. Cannot decrypt without the original salt.")
                    return
            
            for i, file_path in enumerate(files_to_process):
                self.status_updated.emit(f"Processing: {os.path.basename(file_path)}")
                
                if self.operation == 'encrypt':
                    success = self._encrypt_file(file_path, key)
                else:
                    success = self._decrypt_file(file_path, key)
                
                if success:
                    successful_operations += 1
                
                # Update progress
                progress = int((i + 1) / total_files * 100)
                self.progress_updated.emit(progress)
            
            # Clean up salt file after decryption
            if self.operation == 'decrypt' and os.path.exists(salt_file):
                os.remove(salt_file)
            
            if successful_operations == total_files:
                operation_name = "encrypted" if self.operation == 'encrypt' else "decrypted"
                message = f"Successfully {operation_name} {successful_operations} file(s)."
                self.finished_signal.emit(True, message)
            else:
                operation_name = "encryption" if self.operation == 'encrypt' else "decryption"
                message = f"Completed with issues: {successful_operations}/{total_files} files processed successfully."
                self.finished_signal.emit(False, message)
                
        except Exception as e:
            self.finished_signal.emit(False, f"Operation failed: {str(e)}")


class PasswordDialog(QDialog):
    """Dialog for password input."""
    
    def __init__(self, operation="encrypt", parent=None):
        super().__init__(parent)
        self.operation = operation
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle(f"Password for {self.operation.title()}")
        self.setModal(True)
        self.resize(400, 200)
        
        layout = QVBoxLayout()
        
        # Password input
        password_layout = QHBoxLayout()
        password_layout.addWidget(QLabel("Password:"))
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        password_layout.addWidget(self.password_edit)
        layout.addLayout(password_layout)
        
        # Confirm password (only for encryption)
        if self.operation == "encrypt":
            confirm_layout = QHBoxLayout()
            confirm_layout.addWidget(QLabel("Confirm Password:"))
            self.confirm_password_edit = QLineEdit()
            self.confirm_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
            confirm_layout.addWidget(self.confirm_password_edit)
            layout.addLayout(confirm_layout)
        
        # Show password checkbox
        self.show_password_cb = QCheckBox("Show password")
        self.show_password_cb.toggled.connect(self.toggle_password_visibility)
        layout.addWidget(self.show_password_cb)
        
        # Buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.validate_and_accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Focus on password field
        self.password_edit.setFocus()
    
    def toggle_password_visibility(self, checked):
        """Toggle password visibility."""
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self.password_edit.setEchoMode(mode)
        if hasattr(self, 'confirm_password_edit'):
            self.confirm_password_edit.setEchoMode(mode)
    
    def validate_and_accept(self):
        """Validate password input and accept dialog."""
        password = self.password_edit.text()
        
        if not password:
            QMessageBox.warning(self, "Error", "Password cannot be empty.")
            return
        
        if self.operation == "encrypt":
            confirm_password = self.confirm_password_edit.text()
            if password != confirm_password:
                QMessageBox.warning(self, "Error", "Passwords do not match.")
                return
        
        self.accept()
    
    def get_password(self):
        """Get the entered password."""
        return self.password_edit.text()


class ProgressDialog(QDialog):
    """Dialog to show encryption/decryption progress."""
    
    def __init__(self, operation, file_path, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.file_path = file_path
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle(f"{self.operation.title()} Progress")
        self.setModal(True)
        self.resize(500, 200)
        
        layout = QVBoxLayout()
        
        # File info
        file_info = QLabel(f"Processing: {os.path.basename(self.file_path)}")
        layout.addWidget(file_info)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        layout.addWidget(self.progress_bar)
        
        # Status text
        self.status_label = QLabel("Initializing...")
        layout.addWidget(self.status_label)
        
        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button)
        
        self.setLayout(layout)
    
    def update_progress(self, value):
        """Update progress bar."""
        self.progress_bar.setValue(value)
    
    def update_status(self, status):
        """Update status label."""
        self.status_label.setText(status)
    
    def disable_cancel(self):
        """Disable cancel button when operation is finishing."""
        self.cancel_button.setEnabled(False)


class FileEncryptor:
    """Main class for file encryption/decryption functionality."""
    
    def __init__(self, tray_app):
        """Initialize with reference to the main tray app."""
        self.tray_app = tray_app
    
    def encrypt_file_or_folder(self):
        """Show dialog to encrypt a file or folder."""
        file_path = QFileDialog.getExistingDirectory(
            None, 
            "Select folder to encrypt"
        )
        
        if not file_path:
            # Try file selection if no folder selected
            file_path, _ = QFileDialog.getOpenFileName(
                None,
                "Select file to encrypt",
                "",
                "All Files (*)"
            )
        
        if not file_path:
            return
        
        # Show password dialog
        password_dialog = PasswordDialog("encrypt")
        if password_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        password = password_dialog.get_password()
        is_folder = os.path.isdir(file_path)
        
        # Show progress dialog and start encryption
        self._process_file(file_path, password, "encrypt", is_folder)
    
    def decrypt_file_or_folder(self):
        """Show dialog to decrypt a file or folder."""
        file_path = QFileDialog.getExistingDirectory(
            None, 
            "Select folder to decrypt"
        )
        
        if not file_path:
            # Try file selection if no folder selected
            file_path, _ = QFileDialog.getOpenFileName(
                None,
                "Select encrypted file to decrypt",
                "",
                f"Encrypted Files (*{ENC_FILE_SUFFIX});;All Files (*)"
            )
        
        if not file_path:
            return
        
        # Show password dialog
        password_dialog = PasswordDialog("decrypt")
        if password_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        password = password_dialog.get_password()
        is_folder = os.path.isdir(file_path)
        
        # Show progress dialog and start decryption
        self._process_file(file_path, password, "decrypt", is_folder)
    
    def _process_file(self, file_path, password, operation, is_folder):
        """Process file/folder with progress dialog."""
        progress_dialog = ProgressDialog(operation, file_path)
        
        # Create worker thread
        self.worker = EncryptionWorker(operation, file_path, password, is_folder)
        self.worker.progress_updated.connect(progress_dialog.update_progress)
        self.worker.status_updated.connect(progress_dialog.update_status)
        self.worker.finished_signal.connect(lambda success, message: self._on_operation_finished(progress_dialog, success, message))
        
        # Start operation
        self.worker.start()
        progress_dialog.exec()
    
    def _on_operation_finished(self, progress_dialog, success, message):
        """Handle operation completion."""
        progress_dialog.disable_cancel()
        progress_dialog.accept()
        
        if success:
            QMessageBox.information(None, "Success", message)
        else:
            QMessageBox.warning(None, "Error", message)
