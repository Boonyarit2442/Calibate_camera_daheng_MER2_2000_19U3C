## set terminal for run .venv
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

## check py useing from path 
Get-Command python | Select-Object -ExpandProperty Source