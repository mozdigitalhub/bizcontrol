# DigitalOcean Spaces para uploads (media)

Este projeto suporta uploads em bucket da DigitalOcean Spaces quando `USE_SPACES=True`.

## Variáveis de ambiente

Defina no App Platform:

- `USE_SPACES=True`
- `SPACES_ACCESS_KEY=...`
- `SPACES_SECRET_KEY=...`
- `SPACES_BUCKET_NAME=...`
- `SPACES_REGION=nyc3` (exemplo)
- `SPACES_ENDPOINT_URL=https://nyc3.digitaloceanspaces.com`
- `SPACES_LOCATION=media` (opcional, padrão `media`)
- `SPACES_CUSTOM_DOMAIN=...` (opcional, ex.: `cdn.bizcontrol.app` ou `<bucket>.<region>.digitaloceanspaces.com`)
- `SPACES_QUERYSTRING_AUTH=False` (opcional, padrão `False`)
- `SPACES_FILE_OVERWRITE=False` (opcional, padrão `False`)

Compatibilidade: também aceita variáveis AWS equivalentes:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_STORAGE_BUCKET_NAME`
- `AWS_S3_REGION_NAME`

## Comportamento

- Com `USE_SPACES=True`: uploads vão para o Spaces (storage S3).
- Com `USE_SPACES=False`: uploads continuam locais (`MEDIA_ROOT`).

## URL pública dos ficheiros

- Se `SPACES_CUSTOM_DOMAIN` estiver definido, `MEDIA_URL` usa esse domínio.
- Caso contrário, usa o endpoint padrão:
  `https://<region>.digitaloceanspaces.com/<bucket>/<location>/...`

