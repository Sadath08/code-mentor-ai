import sys
import traceback

try:
    from app.main import app
    print("SUCCESS: App loaded correctly.")
except Exception as e:
    with open("out.txt", "w") as f:
        traceback.print_exc(file=f)

