"""
ULTRA SIMPLE TEST - Just check if Dash works at all
"""

import dash
from dash import dcc, html, Input, Output

app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("Click Counter Test"),
    html.Button('Click Me!', id='test-button', n_clicks=0),
    html.Div(id='click-output')
])

@app.callback(
    Output('click-output', 'children'),
    Input('test-button', 'n_clicks')
)
def update_clicks(n_clicks):
    if n_clicks is None or n_clicks == 0:
        return "Button not clicked yet"
    return f"Button clicked {n_clicks} times!"

if __name__ == '__main__':
    print("Starting ultra simple test...")
    print("Open: http://localhost:8052")
    print("If button works, Dash is fine. If not, Dash installation is broken.")
    app.run(debug=True, port=8052)
