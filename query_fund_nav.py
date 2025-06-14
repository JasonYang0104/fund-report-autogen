import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime

# --- 配置区 ---
# 定义要查询的基金代码和对应的名称
fund_name_map = {
    "017437": "华宝纳斯达克精选股票",
    "018064": "华夏标普500ETF联接",
    "050025": "博时标普500ETF联接",
    "000834": "大成纳斯达克100",
    "016055": "博时纳斯达克100ETF联接",
    "017641": "摩根标普500",
    "270042": "广发纳斯达克100ETF联接",
    "040046": "华安纳斯达克100ETF联接",
}

# 获取最近N天的数据
days_to_fetch = 7
# --- 配置区结束 ---

def get_fund_net_value(fund_code: str, days: int) -> pd.DataFrame:
    """获取单个基金指定天数内的历史净值数据"""
    end_date = datetime.datetime.now().strftime("%Y%m%d")
    start_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y%m%d")
    try:
        fund_data = ak.fund_open_fund_info_em(fund_code=fund_code, indicator="单位净值走势")
        fund_data['净值日期'] = pd.to_datetime(fund_data['净值日期'])
        # 筛选指定日期范围内的数据
        mask = (fund_data['净值日期'] >= start_date) & (fund_data['净值日期'] <= end_date)
        return fund_data.loc[mask]
    except Exception as e:
        print(f"获取基金 {fund_code} 数据失败: {e}")
        return pd.DataFrame()

def generate_html_report(all_data_df: pd.DataFrame, fund_info: dict):
    """生成包含表格和交互式图表的HTML报告"""
    # 1. 创建交互式图表
    fig = go.Figure()
    for fund_code, group in all_data_df.groupby('基金代码'):
        fund_name = fund_info.get(fund_code, fund_code)
        fig.add_trace(go.Scatter(
            x=group['净值日期'],
            y=group['单位净值'],
            name=fund_name,
            mode='lines+markers'
        ))

    fig.update_layout(
        title_text='基金单位净值最近走势',
        xaxis_title='日期',
        yaxis_title='单位净值 (CNY)',
        hovermode="x unified", # 统一在x轴显示悬浮信息
        legend_title_text='基金列表',
        font=dict(family="Arial, sans-serif", size=14)
    )
    
    # 悬浮数据模式调整为更精确的 'closest'
    fig.update_layout(hovermode='closest')

    # 将图表转换为HTML代码
    plot_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

    # 2. 创建数据表格
    # 为了报告美观，我们只展示最新的数据
    latest_data = all_data_df.sort_values(by=['基金代码', '净值日期'], ascending=[True, False]).groupby('基金代码').first().reset_index()
    latest_data['基金名称'] = latest_data['基金代码'].map(fund_info)
    # 调整列顺序
    latest_data = latest_data[['基金代码', '基金名称', '净值日期', '单位净值', '日增长率']]
    latest_data['净值日期'] = latest_data['净值日期'].dt.strftime('%Y-%m-%d')
    table_html = latest_data.to_html(index=False, border=0, classes='table table-striped table-hover')


    # 3. 组合成完整的HTML文件
    html_template = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <title>每日基金净值报告</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ padding: 2rem; }}
            .container {{ max-width: 1200px; }}
            h1, h2 {{ text-align: center; margin-bottom: 1.5rem; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>基金净值每日报告</h1>
            <p class="text-center text-muted">报告生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <h2>净值走势图</h2>
            <div class="card mb-4">
                <div class="card-body">
                    {plot_html}
                </div>
            </div>

            <h2>最新净值数据一览</h2>
            <div class="card">
                <div class="card-body">
                    {table_html}
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    with open("fund_report.html", "w", encoding="utf-8") as f:
        f.write(html_template)
    print("HTML报告已生成: fund_report.html")


if __name__ == "__main__":
    all_funds_df_list = []
    for code in fund_name_map.keys():
        df = get_fund_net_value(code, days=days_to_fetch)
        if not df.empty:
            df['基金代码'] = code
            all_funds_df_list.append(df)

    if all_funds_df_list:
        combined_df = pd.concat(all_funds_df_list, ignore_index=True)
        generate_html_report(combined_df, fund_name_map)
    else:
        print("未能获取到任何基金数据，无法生成报告。") 