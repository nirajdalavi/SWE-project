import base64, os
fixed_secret = base64.urlsafe_b64encode(os.urandom(32))
print(fixed_secret)