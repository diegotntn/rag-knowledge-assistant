## Configuración inicial de usuarios (Cognito)

Después de `terraform apply`, Cognito no trae usuarios por default — hay que 
crear al menos uno a mano para poder autenticarse contra la API.

1. Obtén los IDs necesarios:
```powershell
   terraform output user_pool_id
   terraform output user_pool_client_id
```

2. Crea el usuario, asignándole su `tenant_id`:
```powershell
   aws cognito-idp admin-create-user `
     --user-pool-id <user_pool_id> `
     --username <nombre-usuario> `
     --user-attributes Name=email,Value=<correo> Name=email_verified,Value=true Name="custom:tenant_id",Value=<tenant-id> `
     --temporary-password <TempPass123!>
```

3. Fija la contraseña permanente:
```powershell
   aws cognito-idp admin-set-user-password `
     --user-pool-id <user_pool_id> `
     --username <nombre-usuario> `
     --password <PasswordFinal123!> `
     --permanent
```

4. Obtén el token (`IdToken`) para llamar a la API:
```powershell
   aws cognito-idp initiate-auth `
     --client-id <user_pool_client_id> `
     --auth-flow USER_PASSWORD_AUTH `
     --auth-parameters USERNAME=<nombre-usuario>,PASSWORD=<PasswordFinal123!>
```

Nota: este paso es manual a propósito. Un flujo de registro de usuarios 
reales (self-service signup) queda fuera del alcance de este proyecto y 
se cubre en la Fase 7 (frontend).