from flask import Flask, render_template, request, jsonify
import os
import traceback
from database import Database
from face_utils import FaceRecognitionSystem

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Initialize components
db = Database()
face_system = FaceRecognitionSystem()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    
    try:
        data = request.json
        user_id = data.get('user_id')
        username = data.get('username')
        role = data.get('role')
        
        print(f"\n=== Registration Attempt ===")
        print(f"User ID: {user_id}")
        print(f"Username: {username}")
        print(f"Role: {role}")
        
        # Validate input
        if not user_id or not username or not role:
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        if len(user_id) != 4 or not user_id.isdigit():
            return jsonify({'success': False, 'message': 'User ID must be 4 digits'}), 400
        
        # Check if user already exists
        if db.verify_user_exists(user_id):
            return jsonify({'success': False, 'message': 'User ID already exists'}), 400
        
        # Capture face
        try:
            # Capture face encodings
            avg_encoding, all_encodings = face_system.capture_face(num_samples=10)
            
            if avg_encoding is None:
                return jsonify({'success': False, 'message': 'No faces captured. Please try again.'}), 400
            
            # Save face encoding
            encoding_path = face_system.save_encoding(user_id, avg_encoding, all_encodings)
            print(f"Encoding saved to: {encoding_path}")
            
            # Register user in database
            success, result = db.register_user(user_id, username, role, encoding_path)
            
            if success:
                print(f"User registered successfully!")
                return jsonify({'success': True, 'message': 'Registration successful!'})
            else:
                print(f"Registration failed: {result}")
                return jsonify({'success': False, 'message': result}), 400
                
        except Exception as e:
            print(f"Face capture error: {traceback.format_exc()}")
            return jsonify({'success': False, 'message': f'Face capture failed: {str(e)}'}), 400
            
    except Exception as e:
        print(f"Registration error: {traceback.format_exc()}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if request.method == 'GET':
        return render_template('verify.html')
    
    try:
        data = request.json
        user_id = data.get('user_id')
        username = data.get('username')
        role = data.get('role')
        
        print(f"\n=== Verification Attempt ===")
        print(f"User ID: {user_id}")
        print(f"Username: {username}")
        print(f"Role: {role}")
        
        # Validate input
        if not user_id or not username or not role:
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        # Check if user exists
        user = db.get_user(user_id)
        if not user:
            print(f"User not found in database")
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        print(f"Found user: {user['username']} with role {user['role']}")
        
        # Verify user information
        if user['username'] != username or user['role'] != role:
            print(f"Info mismatch: Expected {user['username']}/{user['role']}, got {username}/{role}")
            return jsonify({'success': False, 'message': 'Invalid user information'}), 400
        
        # Perform face verification
        try:
            # Load the face encoding for this user
            known_encoding = face_system.load_encoding(user_id)
            if known_encoding is None:
                print(f"No face encoding found for user {user_id}")
                return jsonify({'success': False, 'message': 'No face data found for user'}), 400
            
            print(f"Face encoding loaded successfully")
            
            # Verify face
            verification_success = face_system.verify_face(user_id, known_encoding)
            
            if verification_success:
                db.update_last_verified(user_id)
                print(f"Verification successful!")
                return jsonify({'success': True, 'message': 'Verification successful!'})
            else:
                db.update_failed_attempt(user_id)
                print(f"Verification failed")
                return jsonify({'success': False, 'message': 'Face verification failed. Please ensure proper lighting, remove glasses/mask, and look directly at the camera.'}), 401
                
        except Exception as e:
            print(f"Face verification error: {traceback.format_exc()}")
            return jsonify({'success': False, 'message': f'Face verification failed: {str(e)}'}), 400
            
    except Exception as e:
        print(f"Verification error: {traceback.format_exc()}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/users')
def get_users():
    try:
        users = db.get_all_users()
        return jsonify({'success': True, 'users': users})
    except Exception as e:
        print(f"Error getting users: {traceback.format_exc()}")
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    print("\n=== Face Authentication System ===")
    print("Starting server...")
    print("Access at: http://localhost:5000")
    print("Make sure your webcam is connected\n")
    app.run(debug=True, host='localhost', port=5000)