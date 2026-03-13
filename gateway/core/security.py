from argon2 import PasswordHasher

# Shared hasher instance — all modules must import from here so argon2
# parameters stay consistent across auth, API key generation, and validation.
ph = PasswordHasher()
