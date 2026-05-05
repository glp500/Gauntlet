### User Input
The user inputs a dataset and a few short specifications in text.

### Data Cleaning
Selects data source, load data, type mappings, data cleaning.

### Data Card
Creates a data card to display key metrics.

### Data Analyst
Analyzes the structure and content of the cleaned dataset. 
Creates a plan for data analysis based on the available data and user specifications.

### Theme
1 out of 5 possible theme presets is chosen based on the tone of the data analysis plan.

### Table Creator
Generates code to create interactive tables which display the contents of the cleaned dataset.

### Chart Orchestrator
Determines how many charts should be displayed based on the data analysis plan and selected theme.
Creates a unique chart creation plan for each chosen chart.

### Chart Makers
One agent is spawned to handle each planned chart.
Agents only follow the plan for their specified chart.
Agents output the code to produce their chart.

### Layout
Congregates data and generation code.
Creates a plan for ordering components.

### UI
All final contents displayed in a jupyter notebook without the code showing by default.
Ordering determined by the layout plan, color palette determined by selected theme. 




