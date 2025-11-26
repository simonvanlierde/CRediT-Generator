import dash
from dash import dcc, html, Input, Output, State, callback_context, dash_table, html
from dash.exceptions import PreventUpdate
import re
import pandas as pd
import numpy as np
import collections
import dash_bootstrap_components as dbc
import json

from lxml import etree
import base64
from io import BytesIO, StringIO
import contextlib
import dash_daq as daq
from app.image_exporter import create_heatmap_bytes, create_heatmap_download

import pprint
pp = pprint.PrettyPrinter(depth=4)

DEFAULT_HEATMAP_COLOR = "#3d94d1"

contributor_roles = {
    'Conceptualization':['Ideas; formulation or evolution of overarching research goals and aims.', 'https://credit.niso.org/contributor-roles/conceptualization/'],
    'Data curation':['Management activities to annotate (produce metadata), scrub data and maintain research data (including software code, where it is necessary for interpreting the data itself) for initial use and later re-use.', 'https://credit.niso.org/contributor-roles/data-curation/'], 
    'Formal Analysis':['Application of statistical, mathematical, computational, or other formal techniques to analyse or synthesize study data.', 'https://credit.niso.org/contributor-roles/formal-analysis/'], 
    'Funding acquisition':['Acquisition of the financial support for the project leading to this publication.', 'https://credit.niso.org/contributor-roles/funding-acquisition/'], 
    'Investigation':['Conducting a research and investigation process, specifically performing the experiments, or data/evidence collection.', 'https://credit.niso.org/contributor-roles/investigation/'], 
    'Methodology':['Development or design of methodology; creation of models.', 'https://credit.niso.org/contributor-roles/methodology/'],
    'Project administration':['Management and coordination responsibility for the research activity planning and execution.', 'https://credit.niso.org/contributor-roles/project-administration/'], 
    'Resources':['Provision of study materials, reagents, materials, patients, laboratory samples, animals, instrumentation, computing resources, or other analysis tools.', 'https://credit.niso.org/contributor-roles/resources/'], 
    'Software':['Programming, software development; designing computer programs; implementation of the computer code and supporting algorithms; testing of existing code components.', 'https://credit.niso.org/contributor-roles/software/'], 
    'Supervision':['Oversight and leadership responsibility for the research activity planning and execution, including mentorship external to the core team.', 'https://credit.niso.org/contributor-roles/supervision/'], 
    'Validation':['Verification, whether as a part of the activity or separate, of the overall replication/reproducibility of results/experiments and other research outputs.', 'https://credit.niso.org/contributor-roles/validation/'], 
    'Visualization':['Preparation, creation and/or presentation of the published work, specifically visualization/data presentation.', 'https://credit.niso.org/contributor-roles/visualization/'],
    'Writing – original draft':['Preparation, creation and/or presentation of the published work, specifically writing the initial draft (including substantive translation).', 'https://credit.niso.org/contributor-roles/writing-original-draft/'], 
    'Writing – review & editing':['Preparation, creation and/or presentation of the published work by those from the original research group, specifically critical review, commentary or revision – including pre- or post-publication stages.', 'https://credit.niso.org/contributor-roles/writing-review-editing/'],
}

df = pd.DataFrame.from_dict(contributor_roles, orient='index', columns=['Description', 'URL'])
df = df.reset_index().rename(columns={'index': 'Role'})
df = df.drop(['URL'], axis=1)

def extract_name_parts(name):
    # Remove special characters and numbers
    name = re.sub(r'[^a-zA-Z\s]', '', name)
    # Split the name into parts
    parts = name.split()
    
    first_name = parts[0] if len(parts) > 0 else ""
    middle_name = parts[1] if len(parts) > 2 else ""
    surname = parts[-1] if len(parts) > 1 else ""
    initials = "".join([part[0] for part in parts if part]).upper()

    return {
        'first_name': first_name,
        'middle_name': middle_name,
        'surname': surname,
        'initials': initials,
        'credit_1': 0,
        'credit_2': 0,
        'credit_3': 0,
        'credit_4': 0,
        'credit_5': 0,
        'credit_6': 0,
        'credit_7': 0,
        'credit_8': 0,
        'credit_9': 0,
        'credit_10': 0,
        'credit_11': 0,
        'credit_12': 0,
        'credit_13': 0,
        'credit_14': 0
    }
    
def generate_unique_initials(authors_dict):
    existing_initials = set()
    
    def create_initials(author):
        first_name = author['first_name']
        middle_name = author['middle_name']
        surname = author['surname']
        
        # Base initials
        initials = (first_name[0] if first_name else '') + (middle_name[0] if middle_name else '') + (surname[0] if surname else '')
        initials = initials.upper()
        
        # Ensure initials are unique by appending characters from the surname
        unique_initials = initials
        if unique_initials:
            while unique_initials in existing_initials:
                if len(unique_initials) < 2 + len(surname):

                    unique_initials = initials + surname[1].lower()  # Use 1 or more characters from surname
                else:
                    unique_initials = initials + str(len(existing_initials))
                
        existing_initials.add(unique_initials)
        return unique_initials

    for key, author in authors_dict.items():
        unique_initials = create_initials(author)
        author['initials'] = unique_initials

def generate_table(dataframe):
    return html.Table(className="table table-header-rotated", children=[
        html.Thead(children=[
            html.Tr(children=[
                html.Th(children=[
                    html.Div(children=[
                        html.Span(col)
                        ])
                    ])
                for col in dataframe.columns
            ])
        ]),
        html.Tbody([
            html.Tr([
                html.Td(
                    children=[html.P(dataframe.iloc[i][dataframe.columns[0]], className='centered-item')], 
                    className='centered-content',
                )] + 
                [
                    html.Td(dbc.Input(
                        id={'type': 'input-text', 'index': i, 'column': generate_id(col)},
                        placeholder=str(dataframe.iloc[i][col]),
                        type="text",
                        value=dataframe.iloc[i][col]
                    )) for col in dataframe.columns[1:5]
                ] +
                [
                    html.Td(className='centered-content', children=[dbc.Checkbox(
                        id={'type': 'input-checkbox', 'index': i, 'column': generate_id(col)},
                        value=bool(dataframe.iloc[i][col]),
                        className='centered-item'
                    )]) for col in dataframe.columns[5:]
                ]
            ) for i in range(len(dataframe))
        ])
    ])

def generate_id(string):
    new = string.lower().replace(' & ', '_').replace(' – ', '_').replace(' ', '_')
    return new

def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)

    try:
        if filename.endswith('.json'):
            json_str = decoded.decode('utf-8')
            json_io = StringIO(json_str)
            df = pd.read_json(json_io)
            df = df.reset_index()
            df = df.rename(columns={df.columns[0]: 'Role'})
            df['Role'] = df['Role'] + 1
            return df
        elif filename.endswith('.xml'):
            root = etree.fromstring(decoded)
            xml_str = etree.tostring(root, pretty_print=True, encoding='unicode')

            data = []
            initials_dict_nested = {}
            for i, contrib in enumerate(root.findall('.//contrib'), start=1):
                given_names = contrib.find('.//given-names').text if contrib.find('.//given-names') is not None else ''
                last_name = contrib.find('.//surname').text if contrib.find('.//surname') is not None else ''

                names = given_names.split(' ')
                n = len(names)
                if n == 1:
                    first_name = names[0]
                    middle_name = ''
                else:
                    first_name = names[0]
                    middle_name = names[1]

                initials_dict_nested[f'author_{i}'] = {
                    'first_name': first_name,
                    'middle_name': middle_name,
                    'surname': last_name
                }
                
                contrib_data = {
                    'First Name': first_name,
                    'Middle Name': middle_name,
                    'Last Name': last_name,
                    'Initials': None
                }
                
                for role in contrib.findall('.//role'):
                    role_name = role.text
                    contrib_data[role_name] = True
                
                data.append(contrib_data)

            df = pd.DataFrame(data)

            generate_unique_initials(initials_dict_nested)
            initials_list = [author_info['initials'] for author_info in initials_dict_nested.values()]
            df['Initials'] = initials_list

            df.iloc[:, :4] = df.iloc[:, :4].fillna('')
            df.iloc[:, 4:] = df.iloc[:, 4:].replace(np.nan, False)

            df = df.reset_index()
            df = df.rename(columns={df.columns[0]: 'Role'})
            df['Role'] = df['Role'] + 1

            df = df[['Role', 'First Name', 'Middle Name', 'Last Name', 'Initials','Conceptualization',
                    'Data curation', 'Formal Analysis', 'Funding acquisition', 'Investigation', 'Methodology',
                    'Project administration', 'Resources', 'Software', 'Supervision', 'Validation', 'Visualization',
                    'Writing – original draft', 'Writing – review & editing']]

            return df
    except Exception as e:
        return f'There was an error processing the file {filename}: {str(e)}'


app = dash.Dash(__name__, suppress_callback_exceptions=True, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "CRediT Generator"
app._favicon = ("favicon.ico")


app.index_string = '''<!DOCTYPE html>
<html>
<head>
  <meta name="author" content="Michaela Vondrackova">
  <meta name="description" content="Generate CRediT paragraphs for scientific publications. Understand Contributor Roles Taxonomy (CRediT) and improve collaboration, citation practices, and transparency in Open Science.">
  <meta name="keywords" content="CRediT, Contributor Roles Taxonomy, Scientific Publication, Open Science, XML JATS4R, Manuscript Contributions, Collaboration, Citation Practices">     
    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-1CCMZG9WQV"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){dataLayer.push(arguments);}
      gtag('js', new Date());

      gtag('config', 'G-1CCMZG9WQV');
    </script>
{%metas%}
<title>{%title%}</title>
{%favicon%}
{%css%}
</head>
<body>
{%app_entry%}
<footer>
{%config%}
{%scripts%}
{%renderer%}
</footer>
</body>
</html>
'''


app.layout = html.Div([
    dbc.Container(children=[
        html.Header(children=[
            html.Img(src='assets/CRediT-solid-01.png', 
                     alt="Logo-CRediT-Generator", 
                     width='25%', 
                     style={
                        'margin-right': '1rem', 
                        'display': 'inline-block', 
                    }),
            html.H2('Generator of CRediT (Contributor Roles Taxonomy) paragraphs for manuscripts', 
                style={
                    'font-family': 'Arial',
                    'font-weight': 'bold',
                    'color':'rgb(61, 148, 209)',
                    'display': 'inline-block',
                    'margin':0,
                }
            ),
        ], style={
                'display': 'flex',
                'align-items': 'center',
                'justify-content': 'flex-start',
                'margin-top': '.5rem',
                'padding': '1rem',
                'border-bottom': '2px solid black'
        }),

        html.Div([
            html.H6([
                html.A('CRediT', href='https://credit.niso.org/'),
                ' (Contributor Roles Taxonomy) is a high-level taxonomy that can be used to represent the roles typically played by contributors to scholarly output. The CRediT Generator prepares the CRediT paragraph for your scientific publication. The names and roles can be saved in a standardized XML file to be reused during the manuscript revision process, to add new authors, or as a source file for journal submission systems. ', html.A('Source code.', href='https://github.com/IPHYS-Bioinformatics/CRediT-Generator')
            ]),

            html.H6('Use this form to summarize author contributions for your manuscript.'),
        ], style={'margin-top':'1rem', 'padding':'1rem'}),


        html.Div(id='form-container', children=[
            
            dbc.Card(
                dbc.CardBody(
                    [
                        html.H4('1A. Paste a list of authors from your Word file', 
                                style={
                                        'font-family': 'Arial',
                                        'color':'rgb(61, 148, 209)'}
                        ),
                        html.Ul([
                            html.Li('Either paste a list of authors directly from a Word file or manually write the names into the text area.'),
                            html.Li('Example below: names, middle names, and surnames separated by "space". Individual authors separated by "comma".'),
                            html.Li('Numbered affiliations and special characters (*#✉) will be removed. Alphabetical affiliations must be removed manually.')
                        ]),
                        dbc.Textarea(
                            id='rawlist',
                            rows=4,
                            #value="Tomas Cajka1#, Jiri Hricko1, Stanislava Rakusanova1, Kristyna Brejchova1, Michaela Novakova1, Lucie Rudl Kulhava1, Veronika Hola1, Michaela Paucova1, Oliver Fiehn2, Ondrej Kuda1*"
                            value="Kristyna Brejchova1#, Veronika Paluchova2, Marie Brezinova2, Tomas Cajka1, Laurence Balas3, Thierry Durand3, Marcela Krizova4, Zbynek Stranak4, Ondrej Kuda5*",
                            style={'margin-bottom':'1rem'}
                        ),
                        dbc.Alert('Done. Proceed to step 2.', id='done-proceed', color="success", style={'display':'none'}),
                        #html.Br(),
                        dbc.Button('Read List', id='read-list-button', n_clicks=0, className='ok_button'),
                    ]
                ), style={'margin-bottom': '1rem'}
            ),

            dbc.Card(
                dbc.CardBody(
                    [
                        html.H4('1B. Or upload your XML or JSON file', style={
                                        'font-family': 'Arial',
                                        'color':'rgb(61, 148, 209)'}),
                        html.Ul([
                            html.Li('This applies if XML or JSON files have been downloaded from this app (see step 3) and if author information needs to be updated.'),
                            html.Li(['XML files may be uploaded from different sources, but they need to be standardized according to the '] + [html.A('JATS4R', href='https://jats4r.niso.org/credit-taxonomy/')] + [' specifications. Use the validator to ensure compliance: '] + [html.A('JATS4R validator', href='https://jats4r-validator.niso.org/')] + ['.']),
                            html.Li(['Download demo ('] + [html.A('demo.json', href='assets/data/demo.json', download='demo.json')] + [', '] + [html.A('demo.xml', href='assets/data/demo.xml', download='demo.xml')] + [') and upload it here.']),
                        ]),
                        dcc.Upload(id='upload-xml-json', children=html.Div([
                            'Drag and Drop or ',
                            html.A('Select Files')
                            ]),
                            style={
                                'width': '100%',
                                'height': '60px',
                                'lineHeight': '60px',
                                'borderWidth': '1px',
                                'borderStyle': 'dashed',
                                'borderRadius': '5px',
                                'textAlign': 'center'}
                        ),
                        html.Div(id='uploaded-filename'),
                        dbc.Alert('Done. Proceed to step 2.', id='done-proceed-upload', color="success", style={'display':'none'})
                    ]
                ), style={'margin-bottom':'1rem'}
            ),

            dbc.Card(
                dbc.CardBody(
                    [
                        html.H4('2. Review the extracted names and fill the generated table', style={
                                        'font-family': 'Arial',
                                        'color':'rgb(61, 148, 209)'}),
                        html.Ul([
                            html.Li('Check if the names were extracted correctly. Update the fields as necessary.'),
                            html.Li('Please review the CRediT guidelines located under the Table of CRediT roles.'),
                            html.Li('Fill the table.'),
                            html.Li('Click "Generate CRediT text for manuscript".')
                        ]),

                        dbc.Accordion(
                                [
                                    dbc.AccordionItem(
                                        [
                                            dash_table.DataTable(
                                                id='contributor-roles-table',
                                                columns=[{"name": i, "id": i} for i in df.columns],
                                                data=df.to_dict('records'),
                                                style_cell={
                                                    'textAlign': 'left', 'padding': '6px', 'border': 'none', 'border-bottom': '1px solid #d9d9d9',
                                                },
                                                style_header={
                                                    'fontWeight': 'bold', 'border': 'none', 'border-bottom': '2px solid black', 'border-top': '2px solid black', 'backgroundColor': 'rgb(255, 255, 255)',
                                                },
                                                style_data_conditional=[
                                                    {
                                                        'if': {'column_id': 'Role'},
                                                        'border-left': 'none'
                                                    },
                                                    {
                                                        'if': {'column_id': 'Link'},
                                                        'border-right': 'none'
                                                    }
                                                ],
                                                style_data={
                                                    'whiteSpace': 'normal',
                                                    'height': 'auto',
                                                }
                                            ),
                                        ], title="Table of CRediT roles"
                                    )
                                ],
                                start_collapsed=False,
                                style={'margin-bottom':'1rem'}
                            ),
                        html.Div(id='table-container'),
                        dcc.Store(id='table-data'),               
                        html.Div([
                            dbc.Button('Generate CRediT text for manuscript', id='generate-button', disabled=True, n_clicks=0, className='ok_button', style={'margin-right':'1rem'}),
                            dbc.Button('Add row', disabled=True, id='add-row'),     
                        ], style={'margin-top':'.5rem'}),
                    ]
                ), style={'margin-bottom':'1rem'}
            ),

            dbc.Card(
                dbc.CardBody(
                    [
                        html.H4('3. CRediT text for manuscript', style={
                                        'font-family': 'Arial',
                                        'color':'rgb(61, 148, 209)'}),
                        html.Ul([
                            html.Li('Copy and paste the CRediT text into the manuscript, download the XML and/or JSON file for further updates.'),
                        ]),
                        dbc.Textarea(
                            id='contributions',
                            rows=3,
                        ),
                        html.Br(),
                        dbc.Textarea(
                            id='contributions-reversed',
                            rows=3,
                        ),
                        html.Br(),
                        dbc.Textarea(
                            id='contributions-reversed-short',
                            rows=3,
                        ),
                        html.P(id='duplicates', className='ok_red'),
                        html.Div([
                            dbc.Button('Download JATS4R XML file', id='generate-jats4r', disabled = True, n_clicks=0, className='ok_button', style={'margin-right':'1rem'}),
                            dcc.Download(id="download-xml"),
                            dbc.Button('Download JSON file', id='generate-json', disabled = True, n_clicks=0, className='ok_button'),
                            dcc.Download(id="download-json"),
                        ], style={'margin-top':'.5rem'}),
                        html.Div([
                            html.I('*', style={'display':'contents'}),
                            html.A('JATS4R XML standard', href='https://jats4r.niso.org/credit-taxonomy/', style={'display':'contents', 'fontStyle': 'italic'}),
                        ], style={'margin-top':'2rem'})
                        
                    ]
                ), style={'margin-bottom':'1rem'}
            )
        ]),

        # Heatmap preview and download
        dbc.Card(
            dbc.CardBody(
                [
                    html.H4("Heatmap preview", style={"font-family": "Arial", "color": "rgb(61, 148, 209)"}),
                    html.Div(
                        [
                            html.Div(
                                [
                                    dbc.Label(
                                        ["Select a ", html.Span("color", id="color")], style={"margin": 0}
                                    ),
                                    dbc.Input(
                                        type="color",
                                        id="color-picker",
                                        value=DEFAULT_HEATMAP_COLOR,
                                        style={
                                            "width": "3.5rem",
                                            "height": "1.5rem",
                                            "padding": "0",
                                            "border": "none",
                                        },
                                    ),
                                ],
                                style={"display": "flex", "align-items": "center", "gap": ".5rem"},
                            ),
                            html.Div(
                                [
                                    html.Span(
                                        "Transpose axes", style={"lineHeight": "1", "display": "inline-block"}
                                    ),
                                    dbc.Checkbox(
                                        id="transpose-check", value=False, style={"margin-left": "0.5rem"}
                                    ),
                                ],
                                style={"display": "flex", "align-items": "center", "margin-left": "1.25rem"},
                            ),
                        ],
                        style={
                            "display": "flex",
                            "align-items": "center",
                            "gap": ".5rem",
                            "margin-bottom": ".5rem",
                        },
                    ),
                    html.Div(
                        html.Img(
                            id="heatmap-preview",
                            src="",
                            style={
                                "maxWidth": "100%",
                                "height": "auto",
                                "border": "1px solid #e6e6e6",
                                "margin-top": ".5rem",
                            },
                        )
                    ),
                    html.Div(
                        [
                            dbc.Button(
                                "Download PNG",
                                id="download-png-btn",
                                n_clicks=0,
                                disabled=True,
                                className="ok_button",
                                style={"margin-right": ".5rem"},
                            ),
                            dbc.Button(
                                "Download PDF",
                                id="download-pdf-btn",
                                n_clicks=0,
                                disabled=True,
                                className="ok_button",
                                style={"margin-right": ".5rem"},
                            ),
                            dcc.Download(id="download-png"),
                            dcc.Download(id="download-pdf"),
                        ],
                        style={"margin-top": ".5rem"},
                    ),
                ]
            ),
            style={"margin-bottom": "1rem"},
        ),

        html.Hr(style={'color':'black', 'opacity':1}),
        html.Div(children=[
            html.H6("Supported by the project National Institute for Research of Metabolic and Cardiovascular Diseases (Programme EXCELES, ID Project No. LX22NPO5104) – Funded by the European Union – Next Generation EU."),
            html.Img(src='assets/3logo_EC_NPO_MSMT_en.jpg', 
                     alt="Logo-CRediT-Generator", 
                     width='50%')
        ], id='credits', style={
            'display': 'flex',
            'flex-direction': 'column',
            'align-items': 'center',
            'justify-content': 'center',
            'text-align': 'center',
        }),
        html.Hr(style={'color':'black', 'opacity':1}),

        html.Div(children=[
                html.A('Laboratory of Metabolism of Bioactive Lipids, Institute of Physiology, Czech Academy of Sciences, 2024', 
                        href='https://www.fgu.cas.cz/en/departments/laboratory-of-metabolism-of-bioactive-lipids',
                        className='footer-link')
                ], 
        style={'text-align':'center', 'margin-bottom':'1rem'}
        )
    ])
])


@app.callback(
    [Output('table-container', 'children'),
     Output('table-data', 'data'),
     Output('generate-button', 'disabled'),
     Output('add-row', 'disabled'),
     Output('done-proceed', 'style'),],
    [Input('read-list-button', 'n_clicks'),
     Input('add-row', 'n_clicks'),
     Input({'type': 'input-text', 'index': dash.dependencies.ALL, 'column': dash.dependencies.ALL}, 'value'),
     Input({'type': 'input-checkbox', 'index': dash.dependencies.ALL, 'column': dash.dependencies.ALL}, 'value'),
     Input('upload-xml-json', 'contents')],
    [State('rawlist', 'value'),
     State('table-data', 'data'),
     State('upload-xml-json', 'filename')]
)
def update_output(read_list, add_row, input_values, checkbox_values, upload_content, rawlist, data, upload_filename):

    ctx = callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    trigger = ctx.triggered[0]['prop_id']

    if trigger == 'read-list-button.n_clicks':
        authors = rawlist    
       
        cleaned_authors = re.sub(r'[^a-zA-Z,\s]', '', authors)
        cleaned_authors2 = re.sub(r',+', ',', cleaned_authors)
        cleaned_authors2 = cleaned_authors2.removesuffix(",")
        
        author_list = [author.strip() for author in cleaned_authors2.split(',')]

        nested_author_dict = {f"author_{i+1}": extract_name_parts(author) for i, author in enumerate(author_list)}

        generate_unique_initials(nested_author_dict)        
        pp.pprint(nested_author_dict)
        
        variables = [
            "role", "first_name", "middle_name", "last_name", "initials", "conceptualization", 
            "data_curation", "formal_analysis", "funding_acquisition", "investigation",
            "methodology", "project_administration", "resources", "software",
            "supervision", "validation", "visualization", "writing_original_draft", "writing_review_editing"
        ]

        data = {variable: [] for variable in variables}

        for idx, (key, author) in enumerate(nested_author_dict.items(), start=1):
            data['role'].append(idx)
            data['first_name'].append(author['first_name'])
            data['middle_name'].append(author['middle_name'])
            data['last_name'].append(author['surname'])
            data['initials'].append(author['initials'])
            data['conceptualization'].append(False)
            data['data_curation'].append(False)
            data['formal_analysis'].append(False)
            data['funding_acquisition'].append(False)
            data['investigation'].append(False)
            data['methodology'].append(False)
            data['project_administration'].append(False)
            data['resources'].append(False)
            data['software'].append(False)
            data['supervision'].append(False)
            data['validation'].append(False)
            data['visualization'].append(False)
            data['writing_original_draft'].append(False)
            data['writing_review_editing'].append(False)

        df = pd.DataFrame(list(zip(data['role'], data['first_name'], data['middle_name'], data['last_name'], data['initials'], 
                                   data['conceptualization'], data['data_curation'], data['formal_analysis'], data['funding_acquisition'], data['investigation'], 
                                   data['methodology'], data['project_administration'], data['resources'], data['software'], data['supervision'], data['validation'], 
                                   data['visualization'], data['writing_original_draft'], data['writing_review_editing'],
                                   )), 
                        columns =['Role', 'First Name', 'Middle Name', 'Last Name', 'Initials','Conceptualization',
                                'Data curation', 'Formal Analysis', 'Funding acquisition', 'Investigation', 'Methodology',
                                'Project administration', 'Resources', 'Software', 'Supervision', 'Validation', 'Visualization',
                                'Writing – original draft', 'Writing – review & editing',])

        return generate_table(df), df.to_dict('records'), False, False, {'display':'block'}
    
    if trigger == 'add-row.n_clicks':
        df = pd.DataFrame(data)
        new_row = dict.fromkeys(df.columns, "")
        new_row['Role'] = len(df) + 1
        new_row = {k: [v] for k, v in new_row.items()}
        df_new_row = pd.DataFrame(new_row)
        df = pd.concat([df, df_new_row], ignore_index=True)
        return generate_table(df), df.to_dict('records'), False, False, {'display':'block'}
    
    if trigger == 'upload-xml-json.contents':
        df = parse_contents(upload_content, upload_filename)
        return generate_table(df), df.to_dict('records'), False, False, dash.no_update
    
    if ("input-text" in trigger) or ("input-checkbox" in trigger):
        input_groups = [input_values[i:i + 4] for i in range(0, len(input_values), 4)]
        checkbox_groups = [checkbox_values[i:i + 14] for i in range(0, len(checkbox_values), 14)]
        
        combined_data = []
        for input_group, checkbox_group in zip(input_groups, checkbox_groups):
            combined_data.append({
                'inputs': input_group,
                'checkboxes': checkbox_group
            })

        output = []
        variables = [
            "role", "first_name", "middle_name", "last_name", "initials", "conceptualization", 
            "data_curation", "formal_analysis", "funding_acquisition", "investigation",
            "methodology", "project_administration", "resources", "software",
            "supervision", "validation", "visualization", "writing_original_draft", "writing_review_editing"
        ]
        d = {variable: [] for variable in variables}
        for i, data in enumerate(combined_data, start=1):
            output.append(f"Inputs: {data['inputs']}, Checkboxes: {data['checkboxes']}")
            d['role'].append(i)
            d['first_name'].append(data['inputs'][0])
            d['middle_name'].append(data['inputs'][1])
            d['last_name'].append(data['inputs'][2])
            d['initials'].append(data['inputs'][3])
            d['conceptualization'].append(data['checkboxes'][0])
            d['data_curation'].append(data['checkboxes'][1])
            d['formal_analysis'].append(data['checkboxes'][2])
            d['funding_acquisition'].append(data['checkboxes'][3])
            d['investigation'].append(data['checkboxes'][4])
            d['methodology'].append(data['checkboxes'][5])
            d['project_administration'].append(data['checkboxes'][6])
            d['resources'].append(data['checkboxes'][7])
            d['software'].append(data['checkboxes'][8])
            d['supervision'].append(data['checkboxes'][9])
            d['validation'].append(data['checkboxes'][10])
            d['visualization'].append(data['checkboxes'][11])
            d['writing_original_draft'].append(data['checkboxes'][12])
            d['writing_review_editing'].append(data['checkboxes'][13])

        update = pd.DataFrame(list(zip(d['role'], d['first_name'], d['middle_name'], d['last_name'], d['initials'], 
                        d['conceptualization'], d['data_curation'], d['formal_analysis'], d['funding_acquisition'], d['investigation'], 
                        d['methodology'], d['project_administration'], d['resources'], d['software'], d['supervision'], d['validation'], 
                        d['visualization'], d['writing_original_draft'], d['writing_review_editing'],
                        )), 
            columns =['Role', 'First Name', 'Middle Name', 'Last Name', 'Initials','Conceptualization',
                    'Data curation', 'Formal Analysis', 'Funding acquisition', 'Investigation', 'Methodology',
                    'Project administration', 'Resources', 'Software', 'Supervision', 'Validation', 'Visualization',
                    'Writing – original draft', 'Writing – review & editing',])

        return generate_table(update), update.to_dict('records'), False, False, dash.no_update
    
    return dash.no_update, dash.no_update, True, True, dash.no_update

@app.callback(Output('uploaded-filename', 'children'),
              Output('done-proceed-upload', 'style'),
              Input('upload-xml-json', 'filename'))
def update_query_output_filename(filename):
    ctx = callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    trigger = ctx.triggered[0]['prop_id']

    if trigger == 'upload-xml-json.filename':
        return [html.Img(src='assets/file-earmark-check.svg', style={'display': 'inline-block', 'margin-right':'.5em'}),
                html.P(filename, style={'display': 'inline-block'})
                ], {'display':'block'}

@app.callback(
    [Output('contributions', 'value'),
     Output('contributions-reversed', 'value'),
     Output('contributions-reversed-short', 'value'),
     Output('generate-jats4r', 'disabled'),
     Output('generate-json', 'disabled'),
     Output('download-png-btn', 'disabled'),
     Output('download-pdf-btn', 'disabled')],
    Input('generate-button', 'n_clicks'),
    Input('table-data', 'data')
)
def update_output(generate_btn, data):
    if generate_btn > 0:

        update = pd.DataFrame(data)
        update = update.drop(columns=update.columns[0], axis=1)

        manuscript = "CRediT: "
        manuscript2 = "CRediT: "
        manuscript3 = "CRediT: "

        for col in update.columns[4:]:
            condition_true = update[col] == True
            if condition_true.empty == False:
                selected_data = update.loc[condition_true, 'Initials']
                manuscript += str(col) + ': ' + ', '.join(selected_data) + '; '

        for i, row in update.iterrows():
            name = ' '.join(row.iloc[:3].fillna(''))
            initials = row.iloc[3]
            selected_cols = [col for col in update.columns[4:] if row[col] == True]
            cols_to_use = ', '.join(selected_cols)

            if selected_cols:
                manuscript2 += f'{name}: {cols_to_use}; '
                manuscript3 += f'{initials}: {cols_to_use}; '

        manuscript2 = manuscript2.replace('  ', ' ')
        manuscript3 = manuscript3.replace('  ', ' ')

        manuscript = manuscript[:-2]
        manuscript2 = manuscript2[:-2]
        manuscript3 = manuscript3[:-2]

        # enable JATS4R / JSON and image downloads when generated
        return manuscript, manuscript2, manuscript3, False, False, False, False

    # keep downloads disabled until the user presses Generate
    return "", "", "", True, True, True, True


@app.callback(
    Output("download-xml", "data"),
    Input('table-data', 'data'),
    Input('generate-jats4r', 'n_clicks'),
    prevent_initial_call=True
)
def update_output(data, jats4r_btn):
    if jats4r_btn > 0:

        update = pd.DataFrame(data)
        update = update.drop(columns=update.columns[0], axis=1)

        doctype = '<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Archiving and Interchange DTD with MathML3 v1.2 20190208//EN" "JATS-archivearticle1-mathml3.dtd">'

        root = etree.Element(
            "article",
            attrib={
                "article-type": "other",
                "dtd-version": "1.2"
            },
            nsmap={
                "xlink": "http://www.w3.org/1999/xlink",
                "ali": "http://www.niso.org/schemas/ali/1.0/"
            }
        )
        front = etree.SubElement(root, "front")
        article_meta = etree.SubElement(front, "article-meta")
        contrib_group = etree.SubElement(article_meta, "contrib-group")

        permission = etree.SubElement(article_meta, "permissions")

        copyright_statement = etree.SubElement(permission, "copyright-statement")
        copyright_year = etree.SubElement(permission, "copyright-year")
        copyright_holder = etree.SubElement(permission, "copyright-holder")

        copyright_statement.text = '© 2019 JATS4R'
        copyright_year.text = '2019'
        copyright_holder.text = 'JATS4R'

        nsmap = {'ali': "http://www.niso.org/schemas/ali/1.0/"}
        license = etree.SubElement(permission, "license", nsmap=nsmap)

        ali_license_ref = etree.SubElement(license, "{http://www.niso.org/schemas/ali/1.0/}license_ref")
        ali_license_ref.text = "http://creativecommons.org/licenses/by/4.0/"

        license_p = etree.SubElement(license, "license-p")
        license_p.text = ("This is an open access article distributed under the terms of the")

        ext_link = etree.SubElement(license_p, "ext-link", nsmap={'xlink': "http://www.w3.org/1999/xlink"})
        ext_link.set("{http://www.w3.org/1999/xlink}href", "http://creativecommons.org/licenses/by/4.0/")
        ext_link.set("ext-link-type", "uri")
        ext_link.text = "Creative Commons Attribution License"

        ext_link.tail = (", which permits unrestricted use, distribution, and reproduction in any medium, provided the original author and source are credited.")
        
        body = etree.SubElement(root, "body")

        for i, row in update.iterrows():
            contrib = etree.SubElement(contrib_group, "contrib", attrib={"contrib-type": "author"},)
            string_name = etree.SubElement(contrib, "string-name")
            given_names = etree.SubElement(string_name, "given-names")
            surname = etree.SubElement(string_name, "surname")

            if row[1] == '':
                given_names.text = row.iloc[0]
            else:
                given_names.text = row.iloc[0] + ' ' + row.iloc[1]

            surname.text = row.iloc[2]

            for col in update.columns[4:]:
                if row[col] == True:
                    role = etree.SubElement(contrib, "role", attrib={
                        'vocab':'credit',
                        'vocab-identifier':'https://credit.niso.org/',
                        'vocab-term': col,
                        'vocab-term-identifier': contributor_roles[col][1],
                        })
                    role.text = col
        
        xml_str = etree.tostring(root, pretty_print=True)
        full_xml_str = f"<?xml version='1.0' encoding='UTF-8'?>\n{doctype}\n{xml_str.decode('utf-8')}"
        file_stream = BytesIO(full_xml_str.encode('utf-8'))
        file_stream.seek(0)
        base64_xml = base64.b64encode(file_stream.read()).decode('utf-8')
        
        return dict(content=base64_xml, filename="credit_result.xml", base64=True)
    
@app.callback(
    Output("download-json", "data"),
    Input('table-data', 'data'),
    Input('generate-json', 'n_clicks'),
    prevent_initial_call=True
)
def update_output(data, json_btn):
    if json_btn > 0:

        update = pd.DataFrame(data)
        update = update.drop(columns=update.columns[0], axis=1)

        json_data = update.to_json(orient='records', indent=4)

        file_stream = BytesIO(json_data.encode('utf-8'))
        file_stream.seek(0)

        base64_json = base64.b64encode(file_stream.read()).decode('utf-8')
        
        return dict(content=base64_json, filename="credit_result.json", base64=True)


@app.callback(
    Output("heatmap-preview", "src"),
    Input("generate-button", "n_clicks"),
    Input("table-data", "data"),
    Input("color-picker", "value"),
    Input("transpose-check", "value"),
)
def update_heatmap_preview(
    generate_btn: int | None,
    table_data: list[dict[str, str | bool]] | None,
    color_value: dict[str, str],
    transpose_value: bool | None, # noqa: FBT001 # Positional boolean argument required for callback functionality in Dash
) -> str:
    """Update the heatmap preview based on the table data and selected color."""
    if not generate_btn or generate_btn <= 0:
        raise PreventUpdate
    if not table_data:
        raise PreventUpdate
    transpose = bool(transpose_value)
    if isinstance(color_value, dict):
        color_hex = color_value.get("hex", DEFAULT_HEATMAP_COLOR)
    else:
        color_hex = color_value or DEFAULT_HEATMAP_COLOR
    png_bytes = create_heatmap_bytes(
        table_data,
        tile_color=color_hex,
        save_format="png",
        transpose=transpose,
    )
    encoded = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@app.callback(
    Output("download-png", "data"),
    Input("download-png-btn", "n_clicks"),
    State("table-data", "data"),
    State("color-picker", "value"),
    State("transpose-check", "value"),
    prevent_initial_call=True,
)
def download_png(
    table_data: list[dict[str, str | bool]] | None,
    color: dict[str, str],
    transpose_value: bool | None,  # noqa: FBT001 # Positional boolean argument required for callback functionality in Dash
) -> dict[str, str | bool]:
    """Download the heatmap as a PNG file."""
    if not table_data:
        raise PreventUpdate
    return create_heatmap_download(
        table_data,
        filename="credit_heatmap.png",
        tile_color=color.get("hex", DEFAULT_HEATMAP_COLOR),
        transpose=bool(transpose_value),
        save_format="png",
    )


@app.callback(
    Output("download-pdf", "data"),
    Input("download-pdf-btn", "n_clicks"),
    State("table-data", "data"),
    State("color-picker", "value"),
    State("transpose-check", "value"),
    prevent_initial_call=True,
)
def download_pdf(
    table_data: list[dict[str, str | bool]] | None,
    color: dict[str, str],
    transpose_value: bool | None,  # noqa: FBT001 # Positional boolean argument required for callback functionality in Dash
) -> dict[str, str | bool]:
    """Download the heatmap as an SVG file."""
    if not table_data:
        raise PreventUpdate
    return create_heatmap_download(
        table_data,
        filename="credit_heatmap.pdf",
        tile_color=color.get("hex", DEFAULT_HEATMAP_COLOR),
        transpose=bool(transpose_value),
        save_format="pdf",
    )


@app.callback(
    Output("download-svg", "data"),
    Input("download-svg-btn", "n_clicks"),
    State("table-data", "data"),
    State("color-picker", "value"),
    State("transpose-check", "value"),
    prevent_initial_call=True,
)
def download_svg(
    table_data: list[dict[str, str | bool]] | None,
    color: dict[str, str],
    transpose_value: bool | None,  # noqa: FBT001 # Positional boolean argument required for callback functionality in Dash
) -> dict[str, str | bool]:
    """Download the heatmap as an SVG file."""
    if not table_data:
        raise PreventUpdate
    return create_heatmap_download(
        table_data,
        filename="credit_heatmap.svg",
        tile_color=color.get("hex", DEFAULT_HEATMAP_COLOR),
        transpose=bool(transpose_value),
        save_format="svg",
    )


def find_duplicates(arr):
    sorted_arr = sorted(arr)
    return [item for item, count in collections.Counter(sorted_arr).items() if count > 1]

if __name__ == '__main__':
    app.run(debug=True)