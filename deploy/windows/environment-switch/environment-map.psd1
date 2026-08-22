@{
    Production = @{
        Label       = "生产环境"
        ProjectRoot = "C:\stockdata\stock_server"
        TaskPrefix  = "StockData"
        Port        = 8899
        LocalPing   = "http://127.0.0.1:8899/ping"
        PublicPing  = "https://api.lifesupermarket.cn/ping"
    }
    Test = @{
        Label       = "测试环境"
        ProjectRoot = "C:\stockdata\stock_server_test"
        TaskPrefix  = "StockDataTest"
        Port        = 8898
        LocalPing   = "http://127.0.0.1:8898/ping"
        PublicPing  = "https://test-api.lifesupermarket.cn/ping"
    }
}
