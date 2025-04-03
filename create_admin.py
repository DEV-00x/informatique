from app import app, db, User

if __name__ == "__main__":
    with app.app_context():
        admin = User(
            username='admin',
            password='admin123',  # في التطبيق الحقيقي، استخدم تشفير كلمة المرور
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin user created successfully!")
