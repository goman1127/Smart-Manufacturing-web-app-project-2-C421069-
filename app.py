import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from scipy.stats import shapiro

st.set_page_config(page_title="스마트제조 품질관리 대시보드", layout="wide")

st.title("🏭 스마트제조 공정능력 및 SPC 대시보드")
st.markdown("데이터를 업로드하여 실시간으로 공정능력(Process Capability)과 통계적공정관리(SPC)를 수행하세요.")

# 1. 사이드바 - 규격(USL, LSL) 및 분석 유형 설정
st.sidebar.header("⚙️ 공정 규격 설정")
usl = st.sidebar.number_input("USL (규격 상한)", value=11.5)
lsl = st.sidebar.number_input("LSL (규격 하한)", value=8.5)

st.sidebar.markdown("---")
analysis_type = st.sidebar.radio("분석 유형 선택", ["공정능력분석 (Capability)", "통계적공정관리 (SPC)"])

chart_choice = None
if analysis_type == "통계적공정관리 (SPC)":
    chart_choice = st.sidebar.selectbox("관리도 선택", ["Xbar-R", "Xbar-s", "P", "NP", "C", "U"])

# 2. 데이터 업로드 및 더미 데이터 생성
st.sidebar.markdown("---")
uploaded_file = st.sidebar.file_uploader("CSV 데이터 업로드 (lot, value 열 필수)", type=['csv'])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.sidebar.success("데이터 로드 완료!")
else:
    st.info("데이터가 없습니다. 테스트용 더미 데이터가 적용되었습니다.")
    np.random.seed(42)
    # lot과 value만 있는 100개의 테스트 데이터 (15번 로트에 의도적 이상치 포함)
    lots = np.repeat(np.arange(1, 21), 5)
    values = np.random.normal(10.0, 0.5, 100)
    values[72] = 13.8 # 의도적 이상치
    df = pd.DataFrame({'lot': lots, 'value': values})

# 🌟 데이터 미리보기 (lot, value)
with st.expander("📋 업로드된 데이터 및 기초 통계량 (단일 소스)", expanded=True):
    col_df, col_stats = st.columns([2, 1])
    with col_df:
        st.dataframe(df, use_container_width=True, height=200)
    with col_stats:
        st.write(df.describe())

# 3. 공정능력분석 로직
if analysis_type == "공정능력분석 (Capability)":
    st.header("📊 공정능력분석 (Process Capability Analysis)")
    
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

    # --- 계량형 관리도 (연속형 데이터 그대로 사용) ---
    if chart_choice in ["Xbar-R", "Xbar-s"]:
        sg = pd.DataFrame()
        sg['Xbar'] = df.groupby('lot')['value'].mean()
        
        n = 5 # 부분군 크기 (과제용 고정)
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

    # --- 계수형 관리도 (USL/LSL 기반 자동 불량 판정 및 집계) ---
    elif chart_choice in ["P", "NP", "C", "U"]:
        # 1. 로트별 표본 크기 계산
        sample_sizes = df.groupby('lot')['value'].count()
        
        # 2. USL을 초과하거나 LSL 미만인 데이터를 '불량'으로 판정하여 개수 집계
        is_defect = (df['value'] > usl) | (df['value'] < lsl)
        defects = df[is_defect].groupby('lot')['value'].count()
        
        # 3. 불량이 없는 로트는 누락되므로 0으로 채움
        defects = defects.reindex(sample_sizes.index, fill_value=0)
        
        # 4. 계수형 연산을 위한 데이터프레임 조립
        attr_df = pd.DataFrame({
            'lot': sample_sizes.index,
            'sample_size': sample_sizes.values,
            'defects': defects.values
        })
        
        total_defects = attr_df['defects'].sum()
        total_samples = attr_df['sample_size'].sum()
        num_lots = len(attr_df)
        
        points = []
        ucl_list, lcl_list = [], []
        cl_line = 0

        if chart_choice == "NP":
            p_bar = total_defects / total_samples
            np_bar = total_defects / num_lots
            points = attr_df['defects']
            cl_line = np_bar
            ucl_line = np_bar + 3 * np.sqrt(np_bar * (1 - p_bar))
            lcl_line = max(0, np_bar - 3 * np.sqrt(np_bar * (1 - p_bar)))
            fig.add_hline(y=ucl_line, line_dash="dash", line_color="red", annotation_text="UCL")
            fig.add_hline(y=lcl_line, line_dash="dash", line_color="red", annotation_text="LCL")

        elif chart_choice == "P":
            p_bar = total_defects / total_samples
            points = attr_df['defects'] / attr_df['sample_size']
            cl_line = p_bar
            ucl_list = p_bar + 3 * np.sqrt((p_bar * (1 - p_bar)) / attr_df['sample_size'])
            lcl_list = np.maximum(0, p_bar - 3 * np.sqrt((p_bar * (1 - p_bar)) / attr_df['sample_size']))
            fig.add_trace(go.Scatter(x=attr_df['lot'], y=ucl_list, mode='lines', line=dict(color='red', dash='dot'), name='UCL'))
            fig.add_trace(go.Scatter(x=attr_df['lot'], y=lcl_list, mode='lines', line=dict(color='red', dash='dot'), name='LCL'))

        elif chart_choice == "C":
            c_bar = attr_df['defects'].mean()
            points = attr_df['defects']
            cl_line = c_bar
            ucl_line = c_bar + 3 * np.sqrt(c_bar)
            lcl_line = max(0, c_bar - 3 * np.sqrt(c_bar))
            fig.add_hline(y=ucl_line, line_dash="dash", line_color="red", annotation_text="UCL")
            fig.add_hline(y=lcl_line, line_dash="dash", line_color="red", annotation_text="LCL")

        elif chart_choice == "U":
            u_bar = total_defects / total_samples
            points = attr_df['defects'] / attr_df['sample_size']
            cl_line = u_bar
            ucl_list = u_bar + 3 * np.sqrt(u_bar / attr_df['sample_size'])
            lcl_list = np.maximum(0, u_bar - 3 * np.sqrt(u_bar / attr_df['sample_size']))
            fig.add_trace(go.Scatter(x=attr_df['lot'], y=ucl_list, mode='lines', line=dict(color='red', dash='dot'), name='UCL'))
            fig.add_trace(go.Scatter(x=attr_df['lot'], y=lcl_list, mode='lines', line=dict(color='red', dash='dot'), name='LCL'))
            
        fig.add_trace(go.Scatter(x=attr_df['lot'], y=points, mode='lines+markers', name='Defects/Rate'))
        fig.add_hline(y=cl_line, line_dash="dash", line_color="green", annotation_text="CL")
        fig.update_layout(title=f"{chart_choice} Control Chart (Derived from USL/LSL)", xaxis_title="Lot", yaxis_title="Defects / Rate")
        

    st.plotly_chart(fig, use_container_width=True)
