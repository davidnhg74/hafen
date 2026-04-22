# Database Connectivity & Credential Management

**How Depart connects to user's Oracle and PostgreSQL databases.**

---

## 🔌 Connection Architecture

### Overview

Depart needs **secure, authenticated connections** to both user's Oracle and PostgreSQL databases. These connections are:
- **User-provided** (not stored on Depart servers)
- **Tested before use** (fail-fast on bad credentials)
- **Pooled for efficiency** (connection pooling)
- **Encrypted in transit** (TLS/SSL)

---

## 1️⃣ Oracle Database Connection

### Setup Requirements

```
User provides:
├─ Host: 192.168.1.100 (or oracle.company.com)
├─ Port: 1521 (default)
├─ Service Name or SID: ORCL
├─ Username: migration_user
└─ Password: [encrypted at rest]
```

### Python Libraries

```toml
# Add to pyproject.toml
oracledb>=2.0.0        # Oracle Python driver (recommended, no client needed)
# OR
cx_Oracle>=8.3         # Older, requires Oracle Instant Client
sqlalchemy[oracle]>=2.0
```

### Connection String Format

```python
# Using oracledb (recommended, simpler)
oracle_url = f"oracle+oracledb://{user}:{password}@{host}:{port}/?service_name={service_name}"

# Example:
# oracle+oracledb://migration_user:password@oracle.company.com:1521/?service_name=ORCL

# Using cx_Oracle (legacy)
oracle_url = f"oracle+cx_oracle://{user}:{password}@{host}:{port}/{service_name}"
```

### Connection Implementation

```python
from sqlalchemy import create_engine, pool, event
from sqlalchemy.exc import OperationalError
import logging

class OracleConnector:
    """Manages Oracle database connections."""
    
    def __init__(self, connection_string: str, pool_size: int = 5, max_overflow: int = 10):
        self.connection_string = connection_string
        self.engine = None
        self.logger = logging.getLogger(__name__)
    
    def connect(self) -> bool:
        """Test connection and create engine."""
        try:
            self.engine = create_engine(
                self.connection_string,
                poolclass=pool.QueuePool,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_pre_ping=True,  # Test connections before use
                echo=False,
                connect_args={
                    "timeout": 30,  # 30 sec timeout
                    "threaded": True,  # Thread-safe
                }
            )
            
            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1 FROM DUAL"))
            
            self.logger.info("✓ Oracle connection successful")
            return True
            
        except OperationalError as e:
            self.logger.error(f"✗ Oracle connection failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"✗ Unexpected error: {e}")
            return False
    
    def get_session(self):
        """Get a new session."""
        if not self.engine:
            raise RuntimeError("Not connected")
        Session = sessionmaker(bind=self.engine)
        return Session()
    
    def close(self):
        """Close connection pool."""
        if self.engine:
            self.engine.dispose()
            self.logger.info("Oracle connection closed")
```

### Oracle Connection Challenges

**Problem 1: Large Result Sets**
```python
# Oracle cursor behavior: fetches all rows at once
# Solution: Use chunked iteration for large tables

def fetch_in_chunks(session, table_name: str, chunk_size: int = 10000):
    """Fetch table in chunks to avoid memory issues."""
    offset = 0
    while True:
        rows = session.execute(text(f"""
            SELECT * FROM {table_name}
            OFFSET {offset} ROWS FETCH NEXT {chunk_size} ROWS ONLY
        """)).fetchall()
        
        if not rows:
            break
        
        yield rows
        offset += chunk_size
```

**Problem 2: Oracle LOB Handling**
```python
# CLOB/BLOB columns require special handling

def read_clob(clob_obj):
    """Read CLOB safely."""
    if clob_obj is None:
        return None
    if isinstance(clob_obj, str):
        return clob_obj
    # CLOB object: read in chunks
    content = ""
    chunk_size = 8192
    for i in range(0, clob_obj.size(), chunk_size):
        content += clob_obj.read(i, chunk_size)
    return content
```

**Problem 3: Oracle Sequences**
```python
# Oracle: SELECT sequence_name.NEXTVAL FROM DUAL
# PostgreSQL: SELECT nextval('sequence_name')

def migrate_sequence(oracle_session, postgres_session, seq_name: str):
    """Migrate sequence and set to current value."""
    # Get current value
    current_val = oracle_session.execute(
        text(f"SELECT {seq_name}.CURRVAL FROM DUAL")
    ).scalar()
    
    # Create in PostgreSQL
    postgres_session.execute(text(f"""
        CREATE SEQUENCE {seq_name} START {current_val};
    """))
```

---

## 2️⃣ PostgreSQL Database Connection

### Setup Requirements

```
User provides:
├─ Host: postgres.company.com
├─ Port: 5432 (default)
├─ Database: depart_migration
├─ Username: postgres
└─ Password: [encrypted]
```

### Python Libraries

```toml
psycopg[binary]>=3.17  # PostgreSQL driver (recommended)
sqlalchemy>=2.0
```

### Connection String Format

```python
# Using psycopg3
postgres_url = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"

# Example:
# postgresql+psycopg://postgres:password@postgres.company.com:5432/depart_migration
```

### Connection Implementation

```python
class PostgresConnector:
    """Manages PostgreSQL database connections."""
    
    def __init__(self, connection_string: str, pool_size: int = 5):
        self.connection_string = connection_string
        self.engine = None
        self.logger = logging.getLogger(__name__)
    
    def connect(self) -> bool:
        """Test connection and create engine."""
        try:
            self.engine = create_engine(
                self.connection_string,
                poolclass=pool.QueuePool,
                pool_size=pool_size,
                max_overflow=10,
                pool_pre_ping=True,
                connect_args={
                    "connect_timeout": 30,
                    "application_name": "depart_migration",
                }
            )
            
            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT version()"))
            
            self.logger.info("✓ PostgreSQL connection successful")
            return True
            
        except OperationalError as e:
            self.logger.error(f"✗ PostgreSQL connection failed: {e}")
            return False
    
    def get_session(self):
        """Get a new session."""
        if not self.engine:
            raise RuntimeError("Not connected")
        Session = sessionmaker(bind=self.engine)
        return Session()
    
    def close(self):
        """Close connection pool."""
        if self.engine:
            self.engine.dispose()
```

---

## 🔐 Credential Management (Critical)

### Secure Storage

**NEVER store plaintext credentials.** Options:

#### Option 1: Environment Variables (Development)
```bash
# .env (local only, never commit)
ORACLE_CONNECTION_STRING=oracle+oracledb://user:pass@host:1521/?service_name=ORCL
POSTGRES_CONNECTION_STRING=postgresql+psycopg://user:pass@host:5432/depart
```

#### Option 2: AWS Secrets Manager (Production)
```python
import boto3
import json

def get_oracle_credentials(secret_name: str) -> dict:
    """Retrieve credentials from AWS Secrets Manager."""
    client = boto3.client('secretsmanager', region_name='us-east-1')
    
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Usage
creds = get_oracle_credentials('depart/oracle/production')
connection_string = f"oracle+oracledb://{creds['username']}:{creds['password']}@..."
```

#### Option 3: HashiCorp Vault (Enterprise)
```python
import hvac

def get_vault_secrets(secret_path: str) -> dict:
    """Retrieve from Vault."""
    client = hvac.Client(url='https://vault.company.com:8200')
    client.auth.approle.login(role_id='...', secret_id='...')
    
    secret = client.secrets.kv.v2.read_secret_data(path=secret_path)
    return secret['data']['data']
```

#### Option 4: User Input (Interactive)
```python
import getpass

def prompt_for_credentials() -> dict:
    """Prompt user for credentials (secure input)."""
    return {
        'host': input("Oracle Host: "),
        'port': input("Oracle Port (1521): ") or "1521",
        'service_name': input("Service Name: "),
        'username': input("Username: "),
        'password': getpass.getpass("Password: "),  # Doesn't echo
    }
```

### Connection String Encryption

```python
from cryptography.fernet import Fernet
import os

class SecureConnectionString:
    """Encrypt/decrypt connection strings at rest."""
    
    def __init__(self):
        # Get key from environment (store in Vault)
        key = os.getenv('ENCRYPTION_KEY')
        self.cipher = Fernet(key)
    
    def encrypt(self, connection_string: str) -> str:
        """Encrypt for storage."""
        return self.cipher.encrypt(connection_string.encode()).decode()
    
    def decrypt(self, encrypted: str) -> str:
        """Decrypt for use."""
        return self.cipher.decrypt(encrypted.encode()).decode()
```

---

## 📝 Connection UI/API

### API Endpoint: Test Connection

```python
class TestConnectionRequest(BaseModel):
    database_type: str  # "oracle" or "postgres"
    host: str
    port: int
    username: str
    password: str
    service_name: str = None  # Oracle only
    database: str = None  # Postgres only

@app.post("/api/v3/connections/test")
async def test_connection(request: TestConnectionRequest) -> dict:
    """Test database connection before migration."""
    try:
        if request.database_type == "oracle":
            conn_str = f"oracle+oracledb://{request.username}:{request.password}@{request.host}:{request.port}/?service_name={request.service_name}"
            connector = OracleConnector(conn_str)
        else:
            conn_str = f"postgresql+psycopg://{request.username}:{request.password}@{request.host}:{request.port}/{request.database}"
            connector = PostgresConnector(conn_str)
        
        success = connector.connect()
        
        if success:
            return {
                "status": "connected",
                "database_type": request.database_type,
                "host": request.host,
                "version": "...",  # Query version
            }
        else:
            return {"status": "failed", "error": "Connection test failed"}
    
    except Exception as e:
        return {"status": "failed", "error": str(e)}
```

### Web UI: Connection Form

```jsx
// React component for connection setup

export function ConnectionSetup() {
  const [dbType, setDbType] = useState('oracle');
  const [formData, setFormData] = useState({
    host: '',
    port: dbType === 'oracle' ? 1521 : 5432,
    username: '',
    password: '',
    serviceName: '',
    database: '',
  });
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState(null);

  const handleTest = async () => {
    setTesting(true);
    const response = await fetch('/api/v3/connections/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        database_type: dbType,
        ...formData,
      }),
    });
    
    const data = await response.json();
    setResult(data);
    setTesting(false);
  };

  return (
    <div className="connection-setup">
      <h2>Database Credentials</h2>
      
      <div className="form-group">
        <label>Database Type</label>
        <select value={dbType} onChange={(e) => setDbType(e.target.value)}>
          <option value="oracle">Oracle Database</option>
          <option value="postgres">PostgreSQL</option>
        </select>
      </div>

      <div className="form-group">
        <label>Host</label>
        <input 
          type="text" 
          value={formData.host}
          onChange={(e) => setFormData({...formData, host: e.target.value})}
          placeholder="oracle.company.com"
        />
      </div>

      <div className="form-group">
        <label>Port</label>
        <input 
          type="number" 
          value={formData.port}
          onChange={(e) => setFormData({...formData, port: parseInt(e.target.value)})}
        />
      </div>

      <div className="form-group">
        <label>Username</label>
        <input 
          type="text" 
          value={formData.username}
          onChange={(e) => setFormData({...formData, username: e.target.value})}
        />
      </div>

      <div className="form-group">
        <label>Password</label>
        <input 
          type="password" 
          value={formData.password}
          onChange={(e) => setFormData({...formData, password: e.target.value})}
        />
      </div>

      {dbType === 'oracle' && (
        <div className="form-group">
          <label>Service Name</label>
          <input 
            type="text" 
            value={formData.serviceName}
            onChange={(e) => setFormData({...formData, serviceName: e.target.value})}
            placeholder="ORCL"
          />
        </div>
      )}

      {dbType === 'postgres' && (
        <div className="form-group">
          <label>Database</label>
          <input 
            type="text" 
            value={formData.database}
            onChange={(e) => setFormData({...formData, database: e.target.value})}
          />
        </div>
      )}

      <button onClick={handleTest} disabled={testing}>
        {testing ? 'Testing...' : 'Test Connection'}
      </button>

      {result && (
        <div className={`result ${result.status}`}>
          {result.status === 'connected' ? (
            <>
              <p>✅ Connected successfully!</p>
              <p>Version: {result.version}</p>
            </>
          ) : (
            <>
              <p>❌ Connection failed</p>
              <p>{result.error}</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
```

---

## ✅ Connection Best Practices

1. **Test Before Migrating**
   - Verify credentials work
   - Check permissions (SELECT, INSERT, CREATE)
   - Verify network connectivity

2. **Use Connection Pooling**
   - SQLAlchemy pools connections automatically
   - Reuse connections across requests
   - Dispose pools on shutdown

3. **Handle Disconnections**
   - Implement retry logic with exponential backoff
   - Detect stale connections (pool_pre_ping=True)
   - Graceful degradation

4. **Monitor Connections**
   - Log all connection events
   - Alert on connection exhaustion
   - Track query performance

5. **Secure Credentials**
   - Never log passwords
   - Encrypt in transit (TLS/SSL)
   - Encrypt at rest (Vault/AWS Secrets)
   - Rotate regularly

---

## 🔄 Connection Workflow

```
1. User provides credentials via UI
   ↓
2. API test connection endpoint
   ├─ Validate format
   ├─ Test connectivity
   ├─ Verify permissions
   └─ Return status
   ↓
3. If success: Store encrypted connection string
   ↓
4. Start migration
   ├─ Oracle: Get table list
   ├─ PostgreSQL: Create destination tables
   └─ Execute migration with pooled connections
   ↓
5. Monitor connections during migration
   ├─ Alert on disconnection
   ├─ Implement retry logic
   └─ Update progress
   ↓
6. Close connection pools on completion
```

---

## 📋 Implementation Checklist

- [ ] Add `oracledb` to pyproject.toml
- [ ] Create OracleConnector class
- [ ] Create PostgresConnector class
- [ ] Implement credential encryption
- [ ] Add test connection endpoint
- [ ] Build connection setup UI
- [ ] Implement connection pooling
- [ ] Add error handling and logging
- [ ] Create AWS Secrets Manager integration (production)
- [ ] Add retry logic with exponential backoff
- [ ] Monitor connection metrics
- [ ] Document connection troubleshooting
