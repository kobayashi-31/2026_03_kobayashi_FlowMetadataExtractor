import sys
token = sys.stdin.read()
print(f"Mock received token of length {len(token)}")
if '!' not in token:
    print("Mock: Token does not contain '!'")
else:
    print("Mock: Token contains '!'")
print(f"Token repr: {repr(token)}")
