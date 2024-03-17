clean:
	powershell remove-item * -include "__pycache__" -Recurse
	powershell remove-item ".mypy_cache" -Recurse
