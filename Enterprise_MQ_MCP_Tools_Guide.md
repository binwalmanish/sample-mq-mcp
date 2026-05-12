# Enterprise IBM MQ MCP Server - Tool Guide
## For Large-Scale Infrastructure (200+ Servers, 500+ Queue Managers)

---

## 📋 Table of Contents

1. [Core Discovery & Health Tools](#core-discovery--health-tools)
2. [Analytics & Trending Tools](#analytics--trending-tools)
3. [Cluster Management Tools](#cluster-management-tools)
4. [Performance & Capacity Tools](#performance--capacity-tools)
5. [Alert & Anomaly Detection](#alert--anomaly-detection)
6. [Batch Operations](#batch-operations)
7. [Integration Recommendations](#integration-recommendations)
8. [Example Use Cases](#example-use-cases)

---

## Core Discovery & Health Tools

### 1. `discover_all_queue_managers()`
**Purpose:** Discover and inventory all queue managers across your entire infrastructure

**When to use:**
- Initial infrastructure discovery
- Daily health checks
- Executive dashboards
- Compliance audits

**Returns:**
- Total count of queue managers
- Running vs stopped status
- Regional distribution
- Environment breakdown (prod/staging/dev)
- Criticality classification

**Example Question:**
> "Show me all queue managers across the infrastructure"
> "How many queue managers are running in us-east region?"
> "List all production queue managers"

---

### 2. `health_check_all_queues(qmgr_name, depth_threshold=80)`
**Purpose:** Comprehensive health check of all queues on a single queue manager

**When to use:**
- Daily operational health checks
- Incident investigation
- Capacity monitoring
- Before maintenance windows

**Detects:**
- ⚠️ Queues above depth threshold (default 80%)
- ⚠️ Queues with messages but no consumers
- 📊 Top 10 queues by depth
- 📈 Total message volumes

**Example Questions:**
> "Check health of QM1"
> "Are there any full queues on PROD_QM_EAST_01?"
> "Show me queues with no consumers on QM_PAYMENTS"

---

### 3. `monitor_channel_status(qmgr_name)`
**Purpose:** Monitor all channels (sender, receiver, cluster, server) for connectivity issues

**When to use:**
- Troubleshooting connectivity issues
- Network problem detection
- Cluster health verification
- Application integration testing

**Detects:**
- ✅ Running channels
- ⚠️ Retrying channels (connection issues)
- ❌ Stopped channels
- ⏸️ Inactive channels

**Example Questions:**
> "Check channel status on QM1"
> "Are there any retrying channels on PROD_QM_WEST_02?"
> "Show me all stopped channels"

---

## Analytics & Trending Tools

### 4. `analyze_queue_depth_trends(qmgr_name, queue_pattern="*")`
**Purpose:** Identify growing queues and predict capacity issues

**When to use:**
- Weekly capacity reviews
- Identifying slow consumers
- Proactive scaling decisions
- Performance optimization

**Analysis:**
- 📈 Queue growth patterns
- 🎯 Capacity utilization percentages
- 💡 Actionable recommendations
- 🔮 Capacity predictions

**Example Questions:**
> "Analyze queue depth trends on QM1"
> "Show me queues that are filling up on ORDERS_QM"
> "Which queues need attention on PROD_QM_EAST_03?"

---

### 5. `get_application_connections(qmgr_name)`
**Purpose:** List all connected applications with connection details

**When to use:**
- Security audits
- Troubleshooting application issues
- Capacity planning for connections
- Identifying unauthorized access

**Returns:**
- Total active connections
- Application names
- User IDs
- IP addresses
- Connection times

**Example Questions:**
> "Show me all applications connected to QM1"
> "How many connections are active on PROD_QM_PAYMENTS?"
> "List connected applications on QM_TRADING"

---

### 6. `check_dead_letter_queues(qmgr_name)`
**Purpose:** Monitor dead letter queues for failed message deliveries

**When to use:**
- Troubleshooting delivery failures
- Identifying problematic applications
- Message routing issues
- Daily operational checks

**Alerts on:**
- Messages in DLQ
- Provides troubleshooting recommendations
- Helps identify root causes

**Example Questions:**
> "Check dead letter queue on QM1"
> "Are there any failed messages on PROD_QM_ORDERS?"
> "Show me DLQ status across all queue managers"

---

## Cluster Management Tools

### 7. `monitor_cluster_health(cluster_name="*")`
**Purpose:** Monitor MQ cluster health across all members

**When to use:**
- Cluster troubleshooting
- Ensuring cluster stability
- Detecting split-brain scenarios
- Verifying cluster repository status

**Monitors:**
- Cluster member status
- Repository queue manager health
- Cluster channel connectivity
- Workload balancing

**Example Questions:**
> "Check health of PROD_CLUSTER"
> "Show me all cluster members and their status"
> "Are there any cluster issues in PAYMENTS_CLUSTER?"

---

## Performance & Capacity Tools

### 8. `get_performance_metrics(qmgr_name)`
**Purpose:** Collect performance metrics for queue manager

**When to use:**
- Performance troubleshooting
- SLA monitoring
- Baseline establishment
- Performance tuning

**Metrics:**
- Queue manager status
- Message processing rates
- Resource utilization
- Performance counters

**Example Questions:**
> "Show me performance metrics for QM1"
> "What's the performance of PROD_QM_TRADING?"
> "Get baseline metrics for capacity planning"

---

### 9. `generate_capacity_report(environment="all")`
**Purpose:** Generate comprehensive capacity planning report

**When to use:**
- Monthly capacity reviews
- Budget planning
- Infrastructure scaling decisions
- Executive reporting

**Includes:**
- Total queue managers by environment
- Total queues and messages
- Regional distribution
- Growth projections
- Scaling recommendations

**Example Questions:**
> "Generate capacity report for production environment"
> "Show me capacity across all environments"
> "What's our current MQ infrastructure utilization?"

---

## Alert & Anomaly Detection

### 10. `detect_anomalies(qmgr_name)`
**Purpose:** Proactively detect unusual behavior and potential issues

**When to use:**
- Automated monitoring (scheduled checks)
- Proactive issue detection
- Preventing incidents
- Early warning system

**Detects:**
- 🔴 CRITICAL: Queues near capacity (>95%)
- 🟠 HIGH: Messages with no consumers
- 🟡 MEDIUM: Old messages aging
- ℹ️ INFO: Unusual patterns

**Example Questions:**
> "Detect any anomalies on QM1"
> "Are there any unusual patterns on PROD_QM_PAYMENTS?"
> "Run anomaly detection across all critical queue managers"

---

## Batch Operations

### 11. `batch_health_check(region="all", criticality="all")`
**Purpose:** Run parallel health checks across multiple queue managers

**When to use:**
- Daily operational health checks
- Executive dashboards
- SLA reporting
- Regional status updates

**Filters:**
- By region (us-east, us-west, eu-west, etc.)
- By criticality (high, medium, low)
- By environment (production, staging, development)

**Returns:**
- Aggregated health status
- Total alerts across all QMs
- Healthy vs problematic queue managers
- Summary by queue manager

**Example Questions:**
> "Run health check on all production queue managers in us-east"
> "Check health of all high-criticality queue managers"
> "Give me a status update on all queue managers"

---

## Integration Recommendations

### For Large-Scale Infrastructure

#### 1. **Configuration Management**
```python
# Instead of hardcoding, load from database or config service
MQ_SERVERS = load_from_database()  # or load_from_consul(), load_from_vault()
```

**Recommended sources:**
- Configuration database (PostgreSQL, MongoDB)
- HashiCorp Consul for service discovery
- HashiCorp Vault for credentials
- CMDB integration

#### 2. **Monitoring Integration**
- **Prometheus**: Export metrics for time-series monitoring
- **Grafana**: Visualize trends and dashboards
- **PagerDuty/Opsgenie**: Alert routing and escalation
- **Datadog/New Relic**: APM integration

#### 3. **Time-Series Database**
Store historical metrics:
- InfluxDB
- TimescaleDB
- Prometheus
- Elasticsearch

#### 4. **Automated Scheduling**
```bash
# Run health checks every hour
0 * * * * claude-cli "Run batch health check on all production queue managers"

# Daily capacity reports
0 8 * * * claude-cli "Generate capacity report for production"

# Anomaly detection every 15 minutes
*/15 * * * * claude-cli "Detect anomalies on all high-criticality queue managers"
```

#### 5. **API Integration**
Expose MCP tools via REST API for:
- ITSM integration (ServiceNow, Jira)
- Custom dashboards
- Mobile applications
- Chatops (Slack, Teams)

#### 6. **Machine Learning Enhancement**
- Train models on historical queue depth patterns
- Predict capacity issues before they occur
- Anomaly detection with ML algorithms
- Automated root cause analysis

---

## Example Use Cases

### Use Case 1: Daily Operations
**Scenario:** Operations team needs morning health report

**Workflow:**
1. Run `batch_health_check(criticality="high")`
2. If alerts found, run `health_check_all_queues()` on affected QMs
3. For connectivity issues, run `monitor_channel_status()`
4. Check `check_dead_letter_queues()` for failed messages

**Sample Question:**
> "Give me the morning health report for all production queue managers"

---

### Use Case 2: Incident Response
**Scenario:** Application reports message delivery failures

**Workflow:**
1. Run `get_application_connections(qmgr_name)` to verify app is connected
2. Run `monitor_channel_status(qmgr_name)` to check connectivity
3. Run `check_dead_letter_queues(qmgr_name)` for failed messages
4. Run `health_check_all_queues(qmgr_name)` to check target queue

**Sample Question:**
> "Our payment application can't send messages to QM_PAYMENTS. What's wrong?"

---

### Use Case 3: Capacity Planning
**Scenario:** Planning infrastructure budget for next year

**Workflow:**
1. Run `generate_capacity_report(environment="production")`
2. Run `analyze_queue_depth_trends()` on high-volume queue managers
3. Review growth patterns over last 12 months
4. Project 20% annual growth

**Sample Question:**
> "Generate annual capacity planning report for all production environments"

---

### Use Case 4: Proactive Monitoring
**Scenario:** Prevent incidents before they occur

**Workflow:**
1. Scheduled `detect_anomalies()` every 15 minutes on critical QMs
2. If anomalies detected, alert operations team
3. Run `analyze_queue_depth_trends()` weekly
4. Review `check_dead_letter_queues()` daily

**Sample Question:**
> "Are there any anomalies that could cause problems in the next hour?"

---

### Use Case 5: Cluster Health
**Scenario:** Ensure cluster is functioning properly

**Workflow:**
1. Run `monitor_cluster_health(cluster_name="PROD_CLUSTER")`
2. Verify all members are connected
3. Check cluster channel status
4. Ensure workload distribution

**Sample Question:**
> "Is our production cluster healthy and properly load-balanced?"

---

### Use Case 6: Security Audit
**Scenario:** Quarterly security review

**Workflow:**
1. Run `get_application_connections()` on all queue managers
2. Verify all connections are authorized
3. Check for unexpected IP addresses
4. Review user IDs and access patterns

**Sample Question:**
> "Show me all application connections across all production queue managers for security audit"

---

## Advanced Features to Consider

### 1. **Multi-Region Support**
```python
# Enhanced configuration with regional awareness
MQ_SERVERS = {
    "us-east": {
        "QM_PROD_01": {...},
        "QM_PROD_02": {...},
    },
    "us-west": {
        "QM_PROD_03": {...},
        "QM_PROD_04": {...},
    },
    "eu-west": {
        "QM_PROD_05": {...},
    }
}
```

### 2. **Automated Remediation**
Add tools for:
- Auto-scaling consumers based on queue depth
- Automatic failover to backup queue managers
- Self-healing for stopped channels
- Auto-purging of old DLQ messages

### 3. **Compliance Reporting**
- Message audit trails
- Access logs
- Configuration change tracking
- SLA compliance metrics

### 4. **Cost Optimization**
- Identify unused queues
- Right-size queue managers
- Optimize message persistence
- Resource utilization tracking

### 5. **Predictive Analytics**
- Machine learning models for capacity prediction
- Anomaly detection with historical baselines
- Automated root cause analysis
- Predictive maintenance

---

## Questions You Can Ask Claude

### Discovery
- "Show me all queue managers"
- "How many queue managers are in production?"
- "List queue managers by region"

### Health Monitoring
- "Check health of QM1"
- "Are there any problematic queues?"
- "Show me all queues over 80% full"

### Troubleshooting
- "Why is my application unable to connect to QM_PAYMENTS?"
- "Are there any channel issues on PROD_QM_EAST_01?"
- "Check the dead letter queue for failed messages"

### Capacity Planning
- "Generate a capacity report for next quarter"
- "Which queue managers need more resources?"
- "Show me queue growth trends"

### Cluster Management
- "Is the production cluster healthy?"
- "Show me all cluster members"
- "Are there any cluster connectivity issues?"

### Security
- "Show me all connected applications"
- "List all connections to production queue managers"
- "Are there any unauthorized connections?"

### Proactive Monitoring
- "Detect any anomalies across all queue managers"
- "What issues might occur in the next hour?"
- "Run daily health check on all critical systems"

---

## Performance Optimization Tips

1. **Caching**: Implement caching for frequently accessed data
2. **Parallel Execution**: Use asyncio for batch operations
3. **Rate Limiting**: Respect MQ REST API rate limits
4. **Connection Pooling**: Reuse HTTP connections
5. **Filtering**: Use queue patterns to reduce data transfer
6. **Pagination**: Implement pagination for large result sets

---

## Best Practices

1. **Regular Monitoring**: Run health checks at least hourly
2. **Alerting**: Set up automated alerts for critical issues
3. **Documentation**: Keep infrastructure configuration up-to-date
4. **Testing**: Test tools in non-production first
5. **Security**: Rotate credentials regularly
6. **Backup**: Maintain configuration backups
7. **Disaster Recovery**: Test failover procedures

---

## Scaling Considerations

For 500+ queue managers:
- Use connection pooling
- Implement distributed caching (Redis)
- Run batch operations in parallel
- Use message queues for async processing
- Implement regional MCP servers
- Use load balancers for API calls
- Consider microservices architecture

---

## Support and Maintenance

### Monitoring the MCP Server
- Log all tool invocations
- Track response times
- Monitor error rates
- Alert on failures

### Updates and Upgrades
- Keep FastMCP framework updated
- Update IBM MQ REST API versions
- Test new features in staging
- Maintain backward compatibility

---

## Conclusion

This enterprise MCP server provides comprehensive tools for managing large-scale IBM MQ infrastructure. By leveraging Claude's natural language interface, operations teams can quickly diagnose issues, perform capacity planning, and maintain healthy messaging infrastructure across hundreds of queue managers.

The tools are designed to be:
- **Scalable**: Handle 500+ queue managers
- **Reliable**: Robust error handling
- **Fast**: Parallel execution where possible
- **Intelligent**: AI-powered analysis and recommendations
- **Actionable**: Clear, actionable insights
