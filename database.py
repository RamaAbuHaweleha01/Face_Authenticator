import sqlite3
import hashlib
import os
from datetime import datetime

class Database:
    def __init__(self, db_path='face_auth.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Create users table
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id_hash TEXT UNIQUE NOT NULL,
                      plain_user_id TEXT NOT NULL,
                      username TEXT NOT NULL,
                      role TEXT NOT NULL,
                      face_model_path TEXT,
                      registered_at TIMESTAMP,
                      last_verified TIMESTAMP,
                      verification_attempts INTEGER DEFAULT 0,
                      failed_attempts INTEGER DEFAULT 0)''')
        
        conn.commit()
        conn.close()
    
    def hash_user_id(self, user_id):
        """Hash the user ID for secure storage"""
        return hashlib.sha256(user_id.encode()).hexdigest()
    
    def register_user(self, user_id, username, role, face_model_path=None):
        """Register a new user"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            hashed_id = self.hash_user_id(user_id)
            c.execute('''INSERT INTO users 
                         (user_id_hash, plain_user_id, username, role, face_model_path, registered_at)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (hashed_id, user_id, username, role, face_model_path, datetime.now()))
            conn.commit()
            return True, hashed_id
        except sqlite3.IntegrityError:
            return False, "User ID already exists"
        except Exception as e:
            return False, str(e)
        finally:
            conn.close()
    
    def get_user(self, user_id):
        """Get user by plain user_id"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            hashed_id = self.hash_user_id(user_id)
            c.execute('SELECT * FROM users WHERE user_id_hash = ?', (hashed_id,))
            row = c.fetchone()
            
            if row:
                # Return user data with plain user_id
                return {
                    'id': row[0],
                    'user_id': row[2],  # plain_user_id
                    'username': row[3],
                    'role': row[4],
                    'face_model_path': row[5],
                    'registered_at': row[6],
                    'last_verified': row[7],
                    'verification_attempts': row[8],
                    'failed_attempts': row[9]
                }
            return None
        except Exception as e:
            print(f"Error getting user: {e}")
            return None
        finally:
            conn.close()
    
    def get_user_by_username(self, username):
        """Get user by username"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute('SELECT * FROM users WHERE username = ?', (username,))
            row = c.fetchone()
            
            if row:
                return {
                    'id': row[0],
                    'user_id': row[2],
                    'username': row[3],
                    'role': row[4],
                    'face_model_path': row[5],
                    'registered_at': row[6],
                    'last_verified': row[7],
                    'verification_attempts': row[8],
                    'failed_attempts': row[9]
                }
            return None
        except Exception as e:
            print(f"Error getting user by username: {e}")
            return None
        finally:
            conn.close()
    
    def update_face_model_path(self, user_id, face_model_path):
        """Update user's face model path"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            hashed_id = self.hash_user_id(user_id)
            c.execute('UPDATE users SET face_model_path = ? WHERE user_id_hash = ?',
                      (face_model_path, hashed_id))
            conn.commit()
        except Exception as e:
            print(f"Error updating face model path: {e}")
        finally:
            conn.close()
    
    def update_last_verified(self, user_id):
        """Update last verification timestamp"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            hashed_id = self.hash_user_id(user_id)
            c.execute('''UPDATE users 
                         SET last_verified = ?, verification_attempts = verification_attempts + 1 
                         WHERE user_id_hash = ?''',
                      (datetime.now(), hashed_id))
            conn.commit()
        except Exception as e:
            print(f"Error updating last verified: {e}")
        finally:
            conn.close()
    
    def update_failed_attempt(self, user_id):
        """Update failed verification attempt"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            hashed_id = self.hash_user_id(user_id)
            c.execute('UPDATE users SET failed_attempts = failed_attempts + 1 WHERE user_id_hash = ?',
                      (hashed_id,))
            conn.commit()
        except Exception as e:
            print(f"Error updating failed attempt: {e}")
        finally:
            conn.close()
    
    def verify_user_exists(self, user_id):
        """Check if user exists by plain user_id"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            hashed_id = self.hash_user_id(user_id)
            c.execute('SELECT COUNT(*) FROM users WHERE user_id_hash = ?', (hashed_id,))
            count = c.fetchone()[0]
            return count > 0
        except Exception as e:
            print(f"Error checking user exists: {e}")
            return False
        finally:
            conn.close()
    
    def get_all_users(self):
        """Get all registered users"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute('SELECT plain_user_id, username, role, registered_at, verification_attempts FROM users')
            rows = c.fetchall()
            
            users = []
            for row in rows:
                users.append({
                    'user_id': row[0],
                    'username': row[1],
                    'role': row[2],
                    'registered_at': row[3],
                    'verification_attempts': row[4]
                })
            return users
        except Exception as e:
            print(f"Error getting all users: {e}")
            return []
        finally:
            conn.close()