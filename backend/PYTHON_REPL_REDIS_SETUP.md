# Python REPL Tool with Redis DataFrame Storage

This document describes the new Python REPL functionality that enables secure code execution with DataFrame analysis using Redis for storage.

## Overview

The system now includes:
- **Redis-based DataFrame storage** for efficient data sharing between tools
- **Secure Python REPL execution** using Docker containers
- **SQL to DataFrame conversion** tool for data preparation
- **Enhanced visualization tools** that use stored DataFrames

## Architecture

```
User Query → sql_db_to_df → Redis Storage → python_repl/large_plotting_tool
                ↓              ↓                    ↓
            SQL Execution  DataFrame ID      Code Execution/Plotting
```

## New Components

### 1. Redis DataFrame Service (`src/services/redis_dataframe_service.py`)

Manages DataFrame storage and retrieval in Redis:

- **Serialization**: Uses pickle for DataFrame storage
- **TTL Management**: Automatic expiration (default: 1 hour)
- **Metadata Storage**: Tracks SQL queries, columns, shape, timestamps
- **Cleanup**: Automatic Redis TTL-based cleanup

**Key Methods:**
- `store_dataframe()` - Store DataFrame with metadata
- `get_dataframe()` - Retrieve DataFrame by ID
- `get_metadata()` - Get DataFrame information
- `extend_ttl()` - Extend DataFrame lifetime
- `delete_dataframe()` - Manual cleanup

### 2. Data Analysis Tools (`src/tools/data_analysis_tools.py`)

#### SqlToDataFrameTool
- Executes SQL queries and stores results in Redis
- Updates agent state with DataFrame context
- Replaces direct SQL execution in visualization tools

#### SecurePythonREPLTool
- Executes Python code in isolated Docker containers
- Loads DataFrames from Redis automatically
- Security features:
  - Container isolation with no network access
  - Memory limits (512MB) and CPU restrictions
  - Read-only filesystem except /tmp
  - Non-root user execution
  - 30-second timeout
  - Automatic container cleanup

#### DataFrameInfoTool
- Provides information about current DataFrame
- Shows metadata, sample data, and statistics

### 3. DataContext Model (`src/models/chat_models.py`)

Encapsulates DataFrame information in agent state:

```python
class DataContext(BaseModel):
    df_id: Optional[str] = None              # Redis key
    sql_query: Optional[str] = None          # Original SQL
    columns: List[str] = []                  # Column names
    shape: Tuple[int, int] = (0, 0)         # Dimensions
    created_at: Optional[datetime] = None    # Creation time
    expires_at: Optional[datetime] = None    # Expiration time
    metadata: Dict[str, Any] = {}            # Additional info
```

### 4. Enhanced Visualization Tools

**LargePlottingTool** now:
- Uses DataFrames from Redis instead of executing SQL
- Automatically extends DataFrame TTL when used
- Maintains all existing plotting functionality

## Configuration

### Docker Compose (`docker-compose.yml`)

```yaml
redis:
  image: redis:7-alpine
  container_name: explainable-agent-redis
  restart: unless-stopped
  ports:
    - "6379:6379"
  command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
  volumes:
    - redis_data:/data
```

### Backend Configuration (`src/models/config.py`)

```python
# Redis Configuration
redis_url: str = "redis://redis:6379"
redis_host: str = "redis"
redis_port: int = 6379
redis_db: int = 0
redis_password: str = ""
redis_ttl: int = 3600  # DataFrame TTL in seconds (1 hour)
```

### Dependencies (`requirements.txt`)

```
redis==5.2.0
docker==7.1.0
```

## Usage Workflow

### 1. Execute SQL and Store DataFrame

```python
# Agent calls sql_db_to_df tool
sql_query = "SELECT customer_id, age, total_spent FROM customers WHERE age > 25"
# Tool stores DataFrame in Redis and updates state
```

### 2. Analyze Data with Python

```python
# Agent calls python_repl tool
code = """
print("DataFrame Info:")
print(f"Shape: {df.shape}")
print(f"Age statistics: {df['age'].describe()}")
print(f"Average spending: ${df['total_spent'].mean():.2f}")

# Calculate correlation
correlation = df['age'].corr(df['total_spent'])
print(f"Age-Spending correlation: {correlation:.3f}")
"""
```

### 3. Create Visualizations

```python
# Agent calls large_plotting_tool
# Uses same DataFrame from Redis automatically
plot_params = {
    "x_column": "age",
    "y_column": "total_spent", 
    "plot_type": "scatter",
    "title": "Customer Age vs Spending"
}
```

## Security Features

### Docker Container Security

- **Isolation**: Each code execution runs in a fresh container
- **Resource Limits**: 512MB RAM, limited CPU shares
- **Network Isolation**: No network access from containers
- **Filesystem**: Read-only except for /tmp (100MB limit)
- **User**: Runs as 'nobody' (non-root)
- **Capabilities**: All Linux capabilities dropped
- **Timeout**: 30-second execution limit
- **Cleanup**: Automatic container removal

### Code Sanitization

- Input sanitization removes common LLM artifacts
- Validates Python syntax before execution
- Captures and returns execution output safely

### Redis Security

- TTL-based automatic cleanup
- No sensitive data persistence beyond session
- Configurable memory limits and eviction policies

## Error Handling

### Common Scenarios

1. **DataFrame Not Available**
   ```
   Error: No DataFrame available. Please run a SQL query first using sql_db_to_df tool.
   ```

2. **DataFrame Expired**
   ```
   Error: DataFrame df_abc123 not found or expired. Please run the SQL query again.
   ```

3. **Docker Issues**
   ```
   Error: Python Docker image not available. Please ensure Docker is running.
   ```

4. **Code Execution Errors**
   ```
   Error: NameError: name 'undefined_var' is not defined
   ```

### Recovery Strategies

- **Expired DataFrames**: Re-run SQL query with sql_db_to_df
- **Docker Issues**: Check Docker daemon and image availability
- **Code Errors**: LLM can see errors and self-correct

## Monitoring and Debugging

### Redis Stats

Use `DataFrameInfoTool` or check Redis directly:

```python
redis_service = get_redis_dataframe_service()
stats = redis_service.get_stats()
print(f"Active DataFrames: {stats['active_dataframes']}")
```

### Logs

Check application logs for:
- DataFrame storage/retrieval operations
- Docker container execution
- Redis connection issues
- TTL extensions and cleanup

### Testing

Run the test suite:

```bash
cd backend
python test_redis_workflow.py
```

## Performance Considerations

### Memory Usage

- **Redis**: Stores serialized DataFrames (pickle format)
- **Containers**: Limited to 512MB each
- **TTL**: Automatic cleanup prevents memory leaks

### Execution Time

- **Container Startup**: ~1-2 seconds per execution
- **DataFrame Loading**: Milliseconds for typical datasets
- **Code Execution**: Depends on complexity (30s timeout)

### Scalability

- **Concurrent Executions**: Docker handles multiple containers
- **Redis Capacity**: Configure based on expected DataFrame sizes
- **TTL Tuning**: Balance between performance and memory usage

## Troubleshooting

### Redis Connection Issues

```bash
# Check Redis connectivity
docker-compose exec backend python -c "import redis; r=redis.from_url('redis://redis:6379'); print(r.ping())"
```

### Docker Issues

```bash
# Check Docker daemon
docker info

# Pull required image
docker pull python:3.11-slim

# Check container permissions
docker run --rm python:3.11-slim python -c "print('Docker works')"
```

### DataFrame Issues

```bash
# Check stored DataFrames
docker-compose exec redis redis-cli keys "df:*"

# Check TTL
docker-compose exec redis redis-cli ttl "df:your_key_here"
```

## Future Enhancements

### Planned Features

1. **Multi-DataFrame Support**: Store and manage multiple DataFrames
2. **Advanced Security**: Additional sandboxing options
3. **Performance Optimization**: Caching and compression
4. **Monitoring Dashboard**: Real-time DataFrame usage stats
5. **Custom Libraries**: Pre-install additional Python packages

### Configuration Options

1. **Container Resources**: Configurable memory/CPU limits
2. **Execution Timeout**: Adjustable timeout values
3. **Redis Persistence**: Optional data persistence
4. **Security Policies**: Customizable container restrictions

## Best Practices

### For Users

1. **DataFrame Lifecycle**: Be aware of TTL limits
2. **Code Efficiency**: Optimize for 30-second timeout
3. **Error Handling**: Check DataFrame availability before analysis
4. **Memory Usage**: Consider DataFrame size for complex operations

### For Developers

1. **Error Messages**: Provide clear, actionable error messages
2. **Logging**: Log all DataFrame operations for debugging
3. **Testing**: Test with various DataFrame sizes and types
4. **Security**: Regularly review container security settings

## Conclusion

The Python REPL tool with Redis DataFrame storage provides a powerful, secure, and efficient way to perform data analysis within the explainable agent framework. The combination of Docker isolation and Redis caching enables complex data analysis while maintaining security and performance.
