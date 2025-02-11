from dash import Dash, dcc, html, Input, Output
import plotly.express as px
import sqlite3
import pandas as pd

# Define a color map for loan statuses
loan_status_colors = {
    "Fully Paid": "blue",
    "Charged Off": "red",
    "Late (31-120 days)": "orange",
    "In Grace Period": "yellow",
    "Late (16-30 days)": "purple",
    "Default": "black",
    "Does not meet the credit policy. Status:Fully Paid": "magenta",
    "Does not meet the credit policy. Status:Charged Off": "green",
    "Current": "lightblue"
}

# Initialize the Dash app
app = Dash(__name__)

# layout of the app
app.layout = html.Div([
    html.H1("Loan Default Risk Dashboard", style={'text-align': 'center'}),
    
    # Dropdown for selecting a credit grade
    html.Div([
        html.Label("Select Credit Grade:"),
        dcc.Dropdown(id="grade-dropdown", options=[], clearable=False)
    ], style={"width": "50%", "margin": "auto", "padding-bottom": "20px"}),

    # Graphs
    dcc.Graph(id="default-rate-graph"),
    dcc.Graph(id="loan-int-graph"),
    dcc.Graph(id="loan-purpose-graph"),
    dcc.Graph(id="time-series-graph"),
    dcc.Graph(id="credit-history-graph")
])

# Callback to populate the dropdown with unique credit grades from the database
@app.callback(
    Output("grade-dropdown", "options"),
    Input("grade-dropdown", "id")  # Dummy input to trigger the callback on load
)
def load_grades(_):
    conn = sqlite3.connect("data/loans50k.db")
    query = "SELECT DISTINCT grade FROM loans50k;"
    df_grades = pd.read_sql(query, conn)
    conn.close()
    return [{"label": g, "value": g} for g in df_grades["grade"].tolist()]

# Callback to update all graphs when a credit grade is selected
@app.callback(
    [
        Output("default-rate-graph", "figure"),
        Output("loan-int-graph", "figure"),
        Output("loan-purpose-graph", "figure"),
        Output("time-series-graph", "figure"),
        Output("credit-history-graph", "figure")
    ],
    [Input("grade-dropdown", "value")]
)
def update_all_graphs(selected_grade):
    # If no grade is selected, default to the first one in the database
    if selected_grade is None:
        conn = sqlite3.connect("data/loans50k.db")
        query = "SELECT DISTINCT grade FROM loans50k LIMIT 1;"
        df_first = pd.read_sql(query, conn)
        conn.close()
        selected_grade = df_first["grade"].iloc[0]
    
    conn = sqlite3.connect("data/loans50k.db")
    
    # --- Graph 1: Default Rates by Loan Amount ---
    query_default = f"""
    SELECT loan_amnt, loan_status FROM loans50k 
    WHERE grade = '{selected_grade}';
    """
    df_default = pd.read_sql(query_default, conn)
    fig_default = px.histogram(
        df_default, x="loan_amnt", color="loan_status",
        title=f"Default Rate by Loan Amount for Grade {selected_grade}",
        labels={"loan_amnt": "Loan Amount ($)"},
        color_discrete_map=loan_status_colors
    )
    
    # --- Graph 2: Loan Amount vs. Interest Rate ---
    query_interest = f"""
    SELECT loan_amnt, int_rate FROM loans50k 
    WHERE grade = '{selected_grade}';
    """
    df_interest = pd.read_sql(query_interest, conn)
    fig_loan_int = px.density_heatmap(
        df_interest, x="loan_amnt", y="int_rate",
        histfunc="count", nbinsx=30, nbinsy=30,
        title=f"Loan Amount vs. Interest Rate (Density) - Grade {selected_grade}"
    )
    
    # --- Graph 3: Loan Purpose Distribution ---
    query_purpose = f"""
    SELECT purpose FROM loans50k 
    WHERE grade = '{selected_grade}';
    """
    df_purpose = pd.read_sql(query_purpose, conn)
    fig_purpose = px.pie(
        df_purpose, names="purpose",
        title=f"Loan Purpose Distribution for Grade {selected_grade}"
    )
    
    # --- Graph 4: Loan Issuance Over Time ---
    query_time_series = f"""
    SELECT issue_d, loan_amnt FROM loans50k 
    WHERE grade = '{selected_grade}';
    """
    df_time_series = pd.read_sql(query_time_series, conn)
    # Let pandas infer the datetime format automatically (since your dates are like "2013-06-01")
    df_time_series["issue_d"] = pd.to_datetime(df_time_series["issue_d"], errors="coerce")
    # Drop rows where the conversion failed
    df_time_series = df_time_series.dropna(subset=["issue_d"])
    # Group by year (using the year extracted from the datetime column)
    if not df_time_series.empty:
        time_series = df_time_series.groupby(df_time_series["issue_d"].dt.year)["loan_amnt"].sum().reset_index()
        # Rename the year column for clarity
        time_series.rename(columns={'issue_d': 'Year'}, inplace=True)
        fig_time_series = px.line(
            time_series, x="Year", y="loan_amnt",
            title="Total Loan Issuance Over Time",
            labels={"loan_amnt": "Total Loan Amount ($)"}
        )
    else:
        # If no data exists, return a default figure
        fig_time_series = px.line(title="Total Loan Issuance Over Time (No Data)")
    
    # --- Graph 5: Borrower Credit History vs. Defaults ---
    query_credit_history = f"""
    SELECT earliest_cr_line, loan_status FROM loans50k 
    WHERE grade = '{selected_grade}';
    """
    df_credit_history = pd.read_sql(query_credit_history, conn)
    # Let pandas infer the datetime format automatically
    df_credit_history["earliest_cr_line"] = pd.to_datetime(df_credit_history["earliest_cr_line"], errors="coerce")
    # Drop rows where conversion failed
    df_credit_history = df_credit_history.dropna(subset=["earliest_cr_line"])
    if not df_credit_history.empty:
        # Group by year and count the loan_status
        credit_trend = df_credit_history.groupby(df_credit_history["earliest_cr_line"].dt.year)["loan_status"].value_counts().unstack().reset_index()
        # Ensure there is a column for "Charged Off"; if not, add it with zeros
        if "Charged Off" not in credit_trend.columns:
            credit_trend["Charged Off"] = 0
        fig_credit_history = px.line(
            credit_trend, x="earliest_cr_line", y="Charged Off",
            title="Loan Defaults vs. Borrower Credit History",
            labels={"earliest_cr_line": "Year", "Charged Off": "Number of Defaults"}
        )
    else:
        fig_credit_history = px.line(title="Loan Defaults vs. Borrower Credit History (No Data)")

    
    conn.close()
    return fig_default, fig_loan_int, fig_purpose, fig_time_series, fig_credit_history

if __name__ == "__main__":
    app.run(debug=True, port=8060)
