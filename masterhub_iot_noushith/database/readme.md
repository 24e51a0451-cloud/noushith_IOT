for activating the database from the server:-
step 1 - open the powershell

$key = "$env:USERPROFILE\OneDrive\Desktop\synapt-db.pem"
icacls $key /inheritance:r
icacls $key /grant:r "$($env:USERNAME):(R)"

step 2 :-
ssh -i "$key" -N -o ExitOnForwardFailure=yes -L 127.0.0.1:15432:synap-postgres.cj0mom00amgu.eu-north-1.rds.amazonaws.com:5432 ec2-user@51.21.170.178

for testing the database:-

Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
$env:PGHOST = "127.0.0.1"
$env:PGPORT = "15432"

python tools/check_postgresql.py