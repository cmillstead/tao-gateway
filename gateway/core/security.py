from argon2 import PasswordHasher

# Shared hasher instance — all modules must import from here so argon2
# parameters stay consistent across auth, API key generation, and validation.
# Parameters are pinned explicitly to prevent silent changes on library upgrades.
ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
