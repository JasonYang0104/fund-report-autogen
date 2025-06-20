import os
# 可选导入 Tushare，仅在环境变量提供 token 时使用
try:
    import tushare as ts
except ImportError:
    ts = None
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
import akshare as ak

# --- 核心配置区 ---

# --- 配置区 ---
# 定义要查询的基金代码和对应的名称
# ts_code 规则：基金代码+".OF"
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

# 初始化 Tushare（如果配置了 token 且库可用）
TS_TOKEN = os.getenv("TUSHARE_TOKEN")
if ts is not None and TS_TOKEN:
    ts.set_token(TS_TOKEN)
    pro = ts.pro_api()
    print("已检测到 Tushare Token，将在 AkShare 无数据时作为备用数据源。")
else:
    pro = None
    print("未配置 Tushare Token，默认仅使用 AkShare 数据源。")

def get_fund_net_value(fund_code: str, days: int) -> pd.DataFrame:
    """获取单个基金指定天数内的历史净值数据 (AkShare 优先)"""
    # 1) AkShare 优先
    try:
        ak_df = ak.fund_open_fund_info_em(fund=fund_code)
        if ak_df is None or ak_df.empty:
            print(f"AkShare 也未取到基金 {fund_code} 数据。")
            return pd.DataFrame()

        ak_df = ak_df[['净值日期', '单位净值']].copy()
        ak_df['净值日期'] = pd.to_datetime(ak_df['净值日期'])
        # 仅保留最近 N 天
        cutoff_dt = datetime.datetime.now() - datetime.timedelta(days=days)
        ak_df = ak_df[ak_df['净值日期'] >= cutoff_dt]
        return ak_df
    except Exception as e:
        print(f"获取基金 {fund_code} 数据失败 (数据源: AkShare): {e}")

    # 2) 若 AkShare 无数据且 Tushare 可用，再尝试 Tushare
    if pro is None:
        print("Tushare Token 未配置，跳过 Tushare 请求。")
        return pd.DataFrame()

    end_date = datetime.datetime.now().strftime("%Y%m%d")
    start_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y%m%d")
    try:
        ts_code = f"{fund_code}.OF"
        fund_data = pro.fund_nav(ts_code=ts_code, start_date=start_date, end_date=end_date)

        if fund_data is not None and not fund_data.empty:
            fund_data = fund_data[['nav_date', 'unit_nav']].rename(columns={'nav_date': '净值日期', 'unit_nav': '单位净值'})
            fund_data['净值日期'] = pd.to_datetime(fund_data['净值日期'])
            return fund_data
        else:
            print(f"Tushare 也未返回基金 {fund_code} 数据。")
            return pd.DataFrame()
    except Exception as e:
        print(f"获取基金 {fund_code} 数据失败 (备用数据源 Tushare): {e}")
        return pd.DataFrame()

def generate_html_report(all_data_df: pd.DataFrame, fund_info: dict):
    """生成包含表格和交互式图表的HTML报告"""
    try:
        print(f"开始生成HTML报告...")
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
        # 调整列顺序，确保'日增长率'存在
        display_columns = ['基金代码', '基金名称', '净值日期', '单位净值']
        if '日增长率' in latest_data.columns:
            display_columns.append('日增长率')
        else:
            # 如果不存在，可能是因为数据源没有提供，给一个默认值
            latest_data['日增长率'] = "N/A"
            display_columns.append('日增长率')
        
        latest_data = latest_data[display_columns]
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

        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html_template)
        print("成功写入 index.html 文件！")
    except Exception as e:
        print(f"生成HTML报告时发生严重错误: {e}")
        # 在遇到错误时，创建一个简单的错误页面，以便我们能看到日志
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(f"<h1>报告生成失败</h1><p>错误详情: {e}</p>")
        raise e # 重新抛出异常，让GitHub Actions知道任务失败了


if __name__ == "__main__":
    try:
        print("--- 开始执行每日基金报告生成任务 ---")
        all_funds_df_list = []
        print(f"待处理基金列表: {list(fund_name_map.keys())}")
        for code in fund_name_map.keys():
            print(f"正在获取基金 {code} 的数据...")
            df = get_fund_net_value(code, days=days_to_fetch)
            if not df.empty:
                print(f"成功获取并处理了基金 {code} 的 {len(df)} 条数据。")
                df['基金代码'] = code
                all_funds_df_list.append(df)
            else:
                print(f"警告: 未能获取到基金 {code} 的数据，可能接口暂时无数据。")

        if all_funds_df_list:
            print("所有基金数据获取完毕，准备合并数据...")
            combined_df = pd.concat(all_funds_df_list, ignore_index=True)
            print("数据合并完成，准备生成HTML报告...")
            generate_html_report(combined_df, fund_name_map)
        else:
            print("错误: 未能获取到任何有效的基金数据，无法生成报告。")
            # 创建一个提示文件，说明没有数据
            with open("index.html", "w", encoding="utf-8") as f:
                f.write("<h1>未能获取到任何基金数据</h1>")

        print("--- 任务执行完毕 ---")
    except Exception as e:
        print(f"脚本主程序发生致命错误: {e}")
        # 同样创建一个错误页面
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(f"<h1>脚本主程序发生致命错误</h1><p>错误详情: {e}</p>")
        # 抛出异常以使CI/CD失败
        raise e 