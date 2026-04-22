# Docker Quick Start

## Start Services

```bash
cd /Users/dnguyen/cld_projects/depart
docker-compose up
```

This starts:
- **PostgreSQL**: localhost:5432 (depart / depart_dev_pw)
- **API**: localhost:8000 (FastAPI with auto-reload)
- **Web**: localhost:3000 (Next.js with hot reload)

## Access Points

### Web Application
- Main app: http://localhost:3000
- Analyzer: http://localhost:3000
- Converter: http://localhost:3000/convert
- Migration Cockpit: http://localhost:3000/migration?workflow_id=YOUR_ID
- ROI Calculator: http://localhost:3000/pricing

### API
- Docs (Swagger): http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/health

### Database
- Connection string: `postgresql://depart:depart_dev_pw@localhost:5432/depart_dev`
- Client: `psql -h localhost -U depart -d depart_dev`

## API Testing

### Create a Workflow
```bash
curl -X POST http://localhost:8000/api/v3/workflow/create \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Migration"}'
```

Response:
```json
{
  "id": "uuid-here",
  "name": "Test Migration",
  "current_step": 1,
  "status": "running",
  ...
}
```

### Get Workflow Status
```bash
curl http://localhost:8000/api/v3/workflow/UUID_FROM_ABOVE
```

### Approve a Step
```bash
curl -X POST http://localhost:8000/api/v3/workflow/UUID/approve/3 \
  -H "Content-Type: application/json" \
  -d '{"approved_by":"John DBA","notes":"Looks good"}'
```

### Test Permissions Analysis
```bash
curl -X POST http://localhost:8000/api/v3/analyze/permissions \
  -H "Content-Type: application/json" \
  -d '{
    "oracle_privileges_json": "{\"system_privs\": [], \"object_privs\": [], \"role_grants\": [], \"dba_users\": [], \"extracted_as_dba\": false}"
  }'
```

## Stop Services
```bash
docker-compose down
```

## View Logs
```bash
docker-compose logs -f api      # API logs
docker-compose logs -f web      # Web logs
docker-compose logs -f postgres # Database logs
```

## Restart Services
```bash
docker-compose restart
```

## Clean Up (Remove volumes)
```bash
docker-compose down -v
```

## Troubleshooting

### Port 3000 or 8000 already in use
```bash
# Find and kill process
lsof -i :3000
kill -9 PID

# Or change port in docker-compose.yml
```

### Database connection fails
```bash
# Check if postgres is healthy
docker-compose ps
docker-compose logs postgres
```

### API startup issues
```bash
# View detailed API logs
docker-compose logs api
```

### Need to rebuild images
```bash
docker-compose build --no-cache
docker-compose up
```
