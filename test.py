"""
SIMPLE UPLOAD TEST
Run this to test if uploads work at all
"""

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import base64

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])

app.layout = dbc.Container([
    html.H1("Upload Test"),

    dcc.Upload(
        id='upload-test',
        children=dbc.Button('Click to Upload File', color='primary', size='lg'),
        multiple=False
    ),

    html.Div(id='upload-result', className='mt-4')
])


@app.callback(
    Output('upload-result', 'children'),
    Input('upload-test', 'contents'),
    State('upload-test', 'filename')
)
def test_upload(contents, filename):
    if contents is None:
        return "No file uploaded yet"

    try:
        # Decode
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)

        # Success
        return dbc.Alert([
            html.H4("✅ SUCCESS!"),
            html.P(f"Filename: {filename}"),
            html.P(f"Size: {len(decoded)} bytes"),
            html.P("Upload callback is WORKING!")
        ], color="success")

    except Exception as e:
        return dbc.Alert([
            html.H4("❌ ERROR"),
            html.P(str(e))
        ], color="danger")


if __name__ == '__main__':
    print("Starting test server...")
    print("Open: http://localhost:8051")
    app.run(debug=True, port=8051)
