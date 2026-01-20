# BizControl API (Tenant Registration)

Endpoint
- `POST /api/v1/tenants/register/`

Request example:

```json
{
  "tenant_name": "Loja Central",
  "tenant_type": "hardware",
  "owner_full_name": "Joao Silva",
  "owner_email": "joao@example.com",
  "owner_phone": "841234567",
  "password": "StrongPass123!",
  "confirm_password": "StrongPass123!",
  "nuit": "123456789",
  "legal_name": "Loja Central, Lda",
  "commercial_registration": "REG-2024-001",
  "country": "MZ",
  "city": "Maputo",
  "address": "Av. 24 de Julho",
  "currency": "MZN",
  "timezone": "Africa/Maputo",
  "accept_terms": true
}
```

Success response (201):

```json
{
  "tenant": { "id": 1, "name": "Loja Central", "type": "hardware", "slug": "loja-central" },
  "owner": { "id": 1, "email": "joao@example.com", "full_name": "Joao Silva" },
  "next": { "login": true },
  "message": "Tenant created successfully"
}
```

Error response (400):

```json
{
  "errors": { "owner_email": ["Nao foi possivel usar este email."] },
  "detail": "Dados invalidos."
}
```
