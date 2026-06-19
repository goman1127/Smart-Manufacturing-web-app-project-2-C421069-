import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from scipy.stats import shapiro, zscore

st.set_page_config(page_title="스마트제조 품질관리 대시보드", layout="wide")

st.title("🏭 스마트제조 공정능력 및 SPC 대시보드")
st.markdown("데이터를 업로드하여 실시간으로 공정능력(Process Capability)과 통계적공정관리(SPC)를 수행하세요.")

# 1. 데이터 업로드 섹션
uploaded_file = st.sidebar.file_uploader("CSV 데이터 파일 업로드", type=['csv'])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.sidebar.success("데이터 로드 완료!")
else:
    st.info("데이터가 없습니다. 좌측에서 CSV 파일을 업로드해주세요. (테스트용 더미 데이터가 표시됩니다)")
    # 테스트용 데이터 생성 (강의록 기반)
    np.random.seed(42)
    df = pd.DataFrame({
        'lot': np.repeat(np.arange(1, 21), 5),
        'value': np.random.normal(10, 1, 100)
    })

# 사이드바 설정
analysis_type = st.sidebar.radio("분석 유형 선택", ["공정능력분석 (Capability)", "통계적공정관리 (SPC)"])

if analysis_type == "공정능력분석 (Capability)":
    st.header("📊 공정능력분석 (Process Capability Analysis)")
    
    col1, col2 = st.columns(2)
    with col1:
        usl = st.number_input("USL (규격 상한)", value=13.0)
    with col2:
        lsl = st.number_input("LSL (규격 하한)", value=7.0)
        
    # 정규성 검정
    stat, p = shapiro(df['value'])
    normality = "만족" if p > 0.05 else "불만족"
    st.write(f"**Shapiro-Wilk 정규성 검정**: p-value = {p:.4f} ({normality})")
    
    # 공정능력지수 계산 (단순화된 예시, 실제 d2/c4 상수는 모듈화 필요)
    x_bar = df['value'].mean()
    sigma_hat = df['value'].std(ddof=1)
    
    cp = (usl - lsl) / (6 * sigma_hat)
    cpk = min((usl - x_bar) / (3 * sigma_hat), (x_bar - lsl) / (3 * sigma_hat))
    
    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    mcol1.metric("Cp", f"{cp:.4f}")
    mcol2.metric("Cpk", f"{cpk:.4f}")
    
    # 히스토그램 생성 (Plotly)
    fig = px.histogram(df, x="value", nbins=20, title='Process Capability Histogram')
    fig.add_vline(x=lsl, line_dash="dash", line_color="red", annotation_text="LSL")
    fig.add_vline(x=usl, line_dash="dash", line_color="red", annotation_text="USL")
    st.plotly_chart(fig, use_container_width=True)

elif analysis_type == "통계적공정관리 (SPC)":
    st.header("📈 통계적공정관리 (Shewhart Control Charts)")
    
    chart_choice = st.selectbox("관리도 선택", ["Xbar-R", "Xbar-s", "P", "NP", "C", "U"])
    
    if chart_choice == "Xbar-R":
        # 군내 평균 및 범위 계산
        sg = pd.DataFrame()
        sg['Xbar'] = df.groupby('lot')['value'].mean()
        sg['R'] = df.groupby('lot')['value'].max() - df.groupby('lot')['value'].min()
        
        x_bar_bar = sg['Xbar'].mean()
        r_bar = sg['R'].mean()
        
        # A2 상수 (표본 크기 5 기준 = 0.577)
        a2 = 0.577
        ucl = x_bar_bar + a2 * r_bar
        lcl = x_bar_bar - a2 * r_bar
        
        # Xbar 차트 시각화
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=sg.index, y=sg['Xbar'], mode='lines+markers', name='Xbar'))
        fig.add_hline(y=x_bar_bar, line_dash="dash", line_color="green", annotation_text="CL")
        fig.add_hline(y=ucl, line_dash="dash", line_color="red", annotation_text="UCL")
        fig.add_hline(y=lcl, line_dash="dash", line_color="red", annotation_text="LCL")
        fig.update_layout(title="Xbar Control Chart", xaxis_title="Lot", yaxis_title="Mean")
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.info("💡 팁: 범위를 벗어난 이상치가 발견되면 해당 로트를 제거하고 관리도를 재작성하는 로직을 추가해 보세요.")