"""
def main():
    print("Hello from feeds-app!")


if __name__ == "__main__":
    main()
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.app:app", host="0.0.0.0", port=8000, reload=True)