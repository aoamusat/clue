"""
Subly - A simple web application for managing subscriptions.
This module serves as the entry point for the application.
It initializes the Flask application and runs the server.
"""

from subly import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
