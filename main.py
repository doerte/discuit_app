# TODO: overall zipFile

from discuit import run
from discuit import data
import pandas as pd
import streamlit as st
from PIL import Image
import write_results

final_output = data.Output(runs=[])

im = Image.open("favicon.ico")
st.set_page_config(
    page_title="Discuit",
    page_icon=im,
    initial_sidebar_state="expanded",
    menu_items={
        # 'Get Help': 'http://link.com',
        'Report a bug': 'https://github.com/doerte/discuit_app/issues',
        'About': "# Discuit  \nPlease cite this app when using it as follows:  \n "
                 "De Kok, D. (2023). _Discuit App [Computer software]_. https://doi.org/10.5281/zenodo.8195514"
        # "  \n  \nContact me at: d.a.de.kok@rug.nl",
    }
)

# build interface and actually run the program
input_d = pd.DataFrame()

col1, col2 = st.columns([1, 3])
col2.title('Discuit')
image = Image.open('discuit-logo.png')
col1.image(image)
df = pd.read_csv("example.csv")

st.write("To start please upload a file containing the data set that needs to be split. You can find information on "
         "the further steps on the left-hand side.")
with st.expander("Show an example of the correct formatting of your .csv file"):
    example = st.dataframe(df, hide_index=True)

col3, col4 = st.sidebar.columns([1, 3])
col3.image(image)
col4.title('Discuit')

st.sidebar.markdown(
    """
**Reference:**  \n
Please cite this app when using it as follows:  \n
De Kok, D. (2023). _Discuit App [Computer software]_. https://doi.org/10.5281/zenodo.8195514

**Steps to take:**
- Upload an input file (.csv) with your items;
""")

col5, col6 = st.sidebar.columns([1, 6])
example_csv = df.to_csv(index=False)
col6.download_button("Download a template*", example_csv, "template", "text/csv", key="template-csv-side")

st.sidebar.markdown(
    """
- Check the preview;
- Select the correct variable types;
- Specify the number of subsets you need;
- Specify the number of set divisions you want to inspect;
- Press the button and wait;
- Check the output and download it.

**Tips:**
- The variable type 'absolute' can be used for (max.) 1 categorical variable that needs to be split between 
sets absolutely even.
- Variable types 'ignore' and 'label' will not be considered when matching sets.
- Selecting a higher number of splits means you will receive more than one possible split and 
then can decide which suits you best.
- If the program fails, try again. If it still fails, try to remove one variable.  \n 

_* Values in template from Brysbaert et al. (2014) for mean concreteness and 
Van Heuven et al. (2014) for Zipf values of word frequency_
"""
)

input_file = st.file_uploader("Upload the .csv file with the input data.", type=["csv"])

if 'split_button' not in st.session_state:
    st.session_state.clicked = False


def click_button():
    st.session_state.clicked = True
    st.cache_data.clear()


def clear_button():
    st.session_state.clicked = False
    st.cache_data.clear()


if input_file is not None:
    filename = input_file.name.removesuffix('.csv')
    data_load_state = st.text('Loading data...')
    input_d = pd.read_csv(input_file)
    # Notify the reader that the data was successfully loaded.
    data_load_state.text('Loading data...done!')

    if input_d is not None:
        if st.checkbox('Show input data', value=True, key="raw_data"):
            st.subheader('Input data')
            st.write(input_d)

        st.subheader("Set your parameters")
        col1, col2 = st.columns([1, 1])
        set_help = "Please select the number of matched sets you need."
        no_sets = col2.slider("Number of output sets", value=2, step=1, min_value=2, max_value=20, key="sets",
                              help=set_help)

        # select variable type per column
        column_list = input_d.columns.values.tolist()
        variables = ["Please select", "numerical", "categorical", "absolute", "ignore", "label"]

        continuous_features = []
        categorical_features = []
        absolute_features = []
        label = []
        disregard = []

        count = 0
        for column in column_list:
            var_help = "Select the data type for this variable: 'label' and 'ignore' will " \
                       "not be considered when making the sets, 'absolut' can only be selected once " \
                       "and should point to a categorical variable that needs to be split perfectly even."
            option = col1.selectbox('Select the type for "' + column + '"', variables, key=column, help=var_help)
            if option == "numerical":
                continuous_features.append(column)
                count = count + 1
            elif option == "categorical":
                categorical_features.append(column)
                count = count + 1
            elif option == "label":
                label.append(column)
                count = count + 1
            elif option == "absolute":
                absolute_features.append(column)
                count = count + 1
            elif option == "ignore":
                disregard.append(column)
                count = count + 1

        it_help = "Please select the number of splits you want to receive. If you select values higher than 1, " \
                  "you will receive multiple output files. You can then choose the best distribution yourself."
        iterations = col2.slider("Number of splits", value=1, step=1, min_value=1, max_value=20, key="iterations",
                                 help=it_help)

        cont = st.container()
        col1, col2 = cont.columns(2)
        button_text = "Create " + str(no_sets) + " sets"
        col1.button(button_text, on_click=click_button, key='split_button')
        x = col2.empty()

        if st.session_state.clicked:
            if count >= len(column_list):
                if len(absolute_features) > 1:
                    st.write(":red[You can only select 1 variable as 'absolute'. Please change your settings.]")
                else:
                    # @st.cache_data(experimental_allow_widgets=True)
                    for it_num in range(iterations):
                        st.write("Making sets... run: ", it_num + 1, " from ", iterations)
                        # initiate loop-tracking
                        i = 0
                        # start first loop
                        output_run = run.run_all(i, it_num, no_sets, input_d, continuous_features, categorical_features,
                                                 label, disregard, absolute_features, filename)
                        key = "clear_Button" + str(it_num)
                        x.button("Clear results", on_click=clear_button, disabled=False, key=key)

                        final_output.runs.append(output_run)
                    write_results.write_to_streamlit(final_output, no_sets)
            else:
                st.write(":red[Please define all variable types!]")
