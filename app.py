import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from scipy.stats import shapiro

st.set_page_config(page_title="스마트제조 품질관리 대시보드", layout="wide")

st.title("🏭 스마트제조 공정능력 및 SPC 대시보드")
st.markdown("데이터를 업로드하여 실시간으로 공정능력(Process Capability)과 통계적공정관리(SPC)를 수행하세요.")

# 1. 사이드바 - 분석 유형 및 차트 선택
analysis_type = st.sidebar.radio("분석 유형 선택", ["공정능력분석 (Capability)", "통계적공정관리 (SPC)"])

chart_choice = None
if analysis_type == "통계적공정관리 (SPC)":
    chart_choice = st.sidebar.selectbox("관리도 선택", ["Xbar-R", "Xbar-s", "P", "NP", "C", "U"])

# 2. 데이터 업로드 및 더미 데이터 생성
uploaded_file = st.sidebar.file_uploader("CSV 데이터 파일 업로드", type=['csv'])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.sidebar.success("데이터 로드 완료!")
else:
    st.info(f"데이터가 없습니다. 현재 '{analysis_type}' 테스트용 더미 데이터로 작동 중입니다.")
    np.random.seed(42)
    
    # 선택된 차트/분석에 따라 적절한 더미 데이터 생성
    if analysis_type == "공정능력분석 (Capability)" or chart_choice in ["Xbar-R", "Xbar-s"]:
        # 계량형 데이터 (로트당 5개 표본)
        df = pd.DataFrame({
            'lot': np.repeat(np.arange(1, 21), 5),
            'value': np.random.normal(10, 1, 100)
        })
    elif chart_choice in ["P", "NP"]:
        # 불량률/불량수 데이터 (로트별 표본 크기와 불량품 수)
        df = pd.DataFrame({
            'lot': np.arange(1, 21),
            'sample_size': np.random.randint(190, 210, 20),
            'count': np.random.binomial(n=200, p=0.05, size=20) # 불량품 수
        })
    elif chart_choice in ["C", "U"]:
        # 결점수 데이터 
        df = pd.DataFrame({
            'lot': np.arange(1, 21),
            'sample_size': np.random.randint(90, 110, 20),
            'count': np.random.poisson(lam=5, size=20) # 결점 수
        })

# 3. 공정능력분석 로직
if analysis_type == "공정능력분석 (Capability)":
    st.header("📊 공정능력분석 (Process Capability Analysis)")
    
    col1, col2 = st.columns(2)
    with col1:
        usl = st.number_input("USL (규격 상한)", value=13.0)
    with col2:
        lsl = st.number_input("LSL (규격 하한)", value=7.0)
        
    stat, p = shapiro(df['value'])
    normality = "만족" if p > 0.05 else "불만족"
    st.write(f"**Shapiro-Wilk 정규성 검정**: p-value = {p:.4f} ({normality})")
    
    x_bar = df['value'].mean()
    sigma_hat = df['value'].std(ddof=1)
    
    cp = (usl - lsl) / (6 * sigma_hat)
    cpk = min((usl - x_bar) / (3 * sigma_hat), (x_bar - lsl) / (3 * sigma_hat))
    
    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    mcol1.metric("Cp", f"{cp:.4f}")
    mcol2.metric("Cpk", f"{cpk:.4f}")
    
    fig = px.histogram(df, x="value", nbins=20, title='Process Capability Histogram')
    fig.add_vline(x=lsl, line_dash="dash", line_color="red", annotation_text="LSL")
    fig.add_vline(x=usl, line_dash="dash", line_color="red", annotation_text="USL")
    st.plotly_chart(fig, use_container_width=True)

# 4. 통계적공정관리(SPC) 로직
elif analysis_type == "통계적공정관리 (SPC)":
    st.header(f"📈 통계적공정관리 - {chart_choice} 관리도")
    
    fig = go.Figure()

    # --- 계량형 관리도 ---
    if chart_choice in ["Xbar-R", "Xbar-s"]:
        sg = pd.DataFrame()
        sg['Xbar'] = df.groupby('lot')['value'].mean()
        
        # 표본 크기가 5라고 가정할 때의 불편화 상수 (실제 환경에서는 동적 계산 필요)
        n = 5 
        a2 = 0.577
        a3 = 1.427
        
        if chart_choice == "Xbar-R":
            sg['R'] = df.groupby('lot')['value'].max() - df.groupby('lot')['value'].min()
            r_bar = sg['R'].mean()
            x_bar_bar = sg['Xbar'].mean()
            
            ucl = x_bar_bar + a2 * r_bar
            lcl = x_bar_bar - a2 * r_bar
            
        elif chart_choice == "Xbar-s":
            sg['s'] = df.groupby('lot')['value'].std(ddof=1)
            s_bar = sg['s'].mean()
            x_bar_bar = sg['Xbar'].mean()
            
            ucl = x_bar_bar + a3 * s_bar
            lcl = x_bar_bar - a3 * s_bar
            
        fig.add_trace(go.Scatter(x=sg.index, y=sg['Xbar'], mode='lines+markers', name='Xbar'))
        fig.add_hline(y=x_bar_bar, line_dash="dash", line_color="green", annotation_text="CL")
        fig.add_hline(y=ucl, line_dash="dash", line_color="red", annotation_text="UCL")
        fig.add_hline(y=lcl, line_dash="dash", line_color="red", annotation_text="LCL")
        fig.update_layout(title=f"{chart_choice} Control Chart", xaxis_title="Lot", yaxis_title="Mean")

    # --- 계수형 관리도 ---
    elif chart_choice in ["P", "NP", "C", "U"]:
        # 데이터프레임 구조: 'lot', 'sample_size', 'count'
        total_count = df['count'].sum()
        total_samples = df['sample_size'].sum()
        num_lots = len(df)
        
        points = []
        ucl_list = []
        lcl_list = []
        cl_line = 0

        if chart_choice == "NP":
            p_bar = total_count / total_samples
            np_bar = df['count'].sum() / num_lots
            points = df['count']
            cl_line = np_bar
            
            # NP는 각 로트별로 LCL/UCL을 계산하거나 평균으로 퉁칠 수 있음. 평균(np_bar) 기준.
            ucl_line = np_bar + 3 * np.sqrt(np_bar * (1 - p_bar))
            lcl_line = max(0, np_bar - 3 * np.sqrt(np_bar * (1 - p_bar)))
            
            fig.add_hline(y=ucl_line, line_dash="dash", line_color="red", annotation_text="UCL")
            fig.add_hline(y=lcl_line, line_dash="dash", line_color="red", annotation_text="LCL")

        elif chart_choice == "P":
            p_bar = total_count / total_samples
            points = df['count'] / df['sample_size']
            cl_line = p_bar
            
            # P 관리도는 각 로트의 sample_size에 따라 UCL/LCL이 변동함
            ucl_list = p_bar + 3 * np.sqrt((p_bar * (1 - p_bar)) / df['sample_size'])
            lcl_list = np.maximum(0, p_bar - 3 * np.sqrt((p_bar * (1 - p_bar)) / df['sample_size']))
            
            fig.add_trace(go.Scatter(x=df['lot'], y=ucl_list, mode='lines', line=dict(color='red', dash='dot'), name='UCL'))
            fig.add_trace(go.Scatter(x=df['lot'], y=lcl_list, mode='lines', line=dict(color='red', dash='dot'), name='LCL'))

        elif chart_choice == "C":
            c_bar = df['count'].mean()
            points = df['count']
            cl_line = c_bar
            
            ucl_line = c_bar + 3 * np.sqrt(c_bar)
            lcl_line = max(0, c_bar - 3 * np.sqrt(c_bar))
            
            fig.add_hline(y=ucl_line, line_dash="dash", line_color="red", annotation_text="UCL")
            fig.add_hline(y=lcl_line, line_dash="dash", line_color="red", annotation_text="LCL")

        elif chart_choice == "U":
            u_bar = total_count / total_samples
            points = df['count'] / df['sample_size']
            cl_line = u_bar
            
            # U 관리도도 각 로트의 sample_size에 따라 UCL/LCL이 변동함
            ucl_list = u_bar + 3 * np.sqrt(u_bar / df['sample_size'])
            lcl_list = np.maximum(0, u_bar - 3 * np.sqrt(u_bar / df['sample_size']))
            
            fig.add_trace(go.Scatter(x=df['lot'], y=ucl_list, mode='lines', line=dict(color='red', dash='dot'), name='UCL'))
            fig.add_trace(go.Scatter(x=df['lot'], y=lcl_list, mode='lines', line=dict(color='red', dash='dot'), name='LCL'))
            
        fig.add_trace(go.Scatter(x=df['lot'], y=points, mode='lines+markers', name='Data Points'))
        fig.add_hline(y=cl_line, line_dash="dash", line_color="green", annotation_text="CL")
        fig.update_layout(title=f"{chart_choice} Control Chart", xaxis_title="Lot", yaxis_title="Value")

    st.plotly_chart(fig, use_container_width=True)
    st.info("💡 팁: P 관리도나 U 관리도처럼 표본 크기(sample_size)가 매 로트마다 다를 경우, 상하한선(UCL, LCL)이 일직선이 아니라 꺾은선 형태로 나타나는 것이 정상입니다.")
