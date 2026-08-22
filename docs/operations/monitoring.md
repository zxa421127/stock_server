# 监控与告警

至少监控：

- `/health/ready` 状态与延迟；
- Gunicorn Worker存活、重启次数、请求耗时和5xx；
- Redis连接、内存、命中率和淘汰数；
- SQLite文件大小、WAL大小、`database is locked`次数和磁盘剩余空间；
- 进程RSS、CPU、线程数、文件描述符；
- 10Mbps出口利用率；
- Nginx 401/403/429/5xx；
- 后台Worker最后成功时间；
- TuShare官网规格扫描失败或待处理变化；
- 接口测试结果目录和日志目录增长。

建议告警阈值：磁盘可用低于20%、连续3次就绪检查失败、Redis不可用、5xx超过1%、429异常激增、Worker 15分钟无心跳、SQLite锁错误持续出现。
