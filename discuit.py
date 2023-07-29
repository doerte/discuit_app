#TODO: overall zipFile

import sys
from typing import List
import pandas as pd
import streamlit as st
from kmodes.kmodes import KModes
from kmodes.kprototypes import KPrototypes
from scipy.stats import chi2_contingency
from scipy.stats import kruskal
from sklearn import metrics
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler
from PIL import Image
import io
import zipfile

input_d = pd.DataFrame()
im = Image.open("favicon.ico")
st.set_page_config(
    page_title="Discuit",
    page_icon=im,
    initial_sidebar_state="expanded",
    menu_items={
        #'Get Help': 'http://link.com',
        'Report a bug': 'https://github.com/doerte/discuit_app/issues',
        'About': "# Discuit  \nPlease cite this app when using it as follows:  \n "
                 "De Kok, D. (2023). _Discuit App [Computer software]_. https://doi.org/10.5281/zenodo.8195515"
                 #"  \n  \nContact me at: d.a.de.kok@rug.nl",
    }
)

def prepare_data(data, continuous, categorical, label, disregard):
    # remove label column & disregarded columns
    if len(label) != 0:
        data = data.drop([label[0]], axis=1)
    if len(disregard) != 0:
        data = data.drop(disregard, axis=1)
    # transform continuous data
    if len(continuous) != 0:
        #replace md with average
        for feat in continuous:
            data[feat].fillna(data[feat].mean(), inplace=True)
        mms = MinMaxScaler()
        data[continuous] = mms.fit_transform(data[continuous])
    # make sure categorical data uses numbers (for silhouette score)
    if len(categorical) != 0:
        for feat in categorical:
            # replace missing data with dummy category
            data[feat].fillna("missingData", inplace=True)
            if data[feat].dtype not in ("float64", "int64"):
                # find unique values
                values = data[feat].unique()
                i = 0
                # replace values
                for value in values:
                    data[feat].replace(value, i, inplace=True)
                    i=i+1
    return data


def clustering(transformed_data, categorical_features, continuous_features):
    # determine max number of clusters...
    max_clus = int(len(transformed_data) * .5)
    max_clus = min(max_clus, 10)
    cl_range = range(2, max_clus)  # changed to max 10 clusters to keep speed, check which max is appropriate
    # kmodes prototype for mixed numerical and categorical data
    largest_sil = (0, -1)

    # this needs to be adjusted depending on input
    categorical_features_idx = [transformed_data.columns.get_loc(col) for col in categorical_features]
    mark_array = transformed_data.values

    # choose algorithm depending on input
    if (len(categorical_features) != 0) and (len(continuous_features) != 0):
        for k in cl_range:
            kproto = KPrototypes(n_clusters=k, max_iter=20)
            kproto.fit_predict(mark_array, categorical=categorical_features_idx)
            sil = metrics.silhouette_score(transformed_data, kproto.labels_, sample_size=1000)
            if sil > largest_sil[1]:
                largest_sil = (k, sil)
        kproto_final = KPrototypes(n_clusters=largest_sil[0], max_iter=20)

        pred_cluster = kproto_final.fit_predict(mark_array, categorical=categorical_features_idx)

    elif (len(categorical_features) != 0) and (len(continuous_features) == 0):
        for k in cl_range:
            kmode = KModes(n_clusters=k, init="random", n_init=5)
            kmode.fit_predict(transformed_data)
            sil = metrics.silhouette_score(transformed_data, kmode.labels_, sample_size=1000)
            if sil > largest_sil[1]:
                largest_sil = (k, sil)
        kmode_final = KModes(n_clusters=largest_sil[0], init="random", n_init=5)
        pred_cluster = kmode_final.fit_predict(transformed_data)
    else:
        for k in cl_range:
            km = KMeans(n_clusters=k, n_init=1, init='k-means++')
            km.fit_predict(transformed_data)
            sil = metrics.silhouette_score(transformed_data, km.labels_, sample_size=1000)
            if sil > largest_sil[1]:
                largest_sil = (k, sil)
        km_final = KMeans(n_clusters=largest_sil[0], init='k-means++', n_init=1)
        pred_cluster = km_final.fit_predict(transformed_data)

    clusters: List[List[int]] = [[] for _ in range(largest_sil[0])]

    for i, cluster in enumerate(pred_cluster):
        clusters[cluster].append(i)

    final_clusters = []

    for cluster in clusters:
        cluster_new = []
        for item in cluster:
            cluster_new.append(transformed_data.iloc[item].name)
        final_clusters.append(cluster_new)

    return final_clusters

def divide_in_sets(clusters, output_sets):
    # divide clusters evenly amongst desired sets
    for cluster in clusters:
        for item in cluster:
            output_sets[output_sets.index(min(output_sets, key=len))].append(item)


def split(absolute, data):
    try:
        grouped = data.groupby(absolute)
    except KeyError:
        print('You listed an absolute variable that cannot be found in the input file')
        sys.exit(1)  # abort

    data_splitted = []
    for _, group in grouped:
        # drop absolute columns from further analysis
        data_x = group.drop(columns=absolute)
        data_splitted.append(data_x)

    return data_splitted


def kwtest(label, features, sets, data):
    stats = []
    df = len(sets) - 1
    for feat in features:
        kw_input = []
        for s_set in sets:
            itemlist = data.loc[data.set_number == s_set, feat].tolist()
            kw_input.append(itemlist)
        stat, p = kruskal(*kw_input)
        stats.append([label, "Kruskal-Wallis test", feat, stat, df, p])
    return stats


def chi(label, features, data):
    stats = []
    for feat in features:
        data_crosstab = pd.crosstab(data[feat],
                                    data['set_number'])

        # check expected values and only use yates correction if any exp value < 5
        _, _, _, exp = chi2_contingency(data_crosstab)
        yates = False
        test = "Chi2-Test"

        for exp_list in exp:
            if any(x < 5 for x in exp_list):
                yates = True
                test = "Chi2-Test with Yates correction"

        stat, p, dof, _ = chi2_contingency(data_crosstab, correction=yates)

        stats.append([label, test, feat, stat, dof, p])

    return stats


def statistics(data):
    stats_out = []
    subsets = []
    if len(absolute_features) > 0:
        subsets = data[absolute_features[0]].unique()
    sets = data.set_number.unique()

    # overall stats
    stats_out.append(kwtest("overall", continuous_features, sets, data))
    stats_out.append(chi("overall", categorical_features, data))
    stats_out.append(chi("overall", absolute_features, data))

    for subset in subsets:
        stats_frame = data.loc[data[absolute_features[0]] == subset]
        stats_out.append(kwtest(subset, continuous_features, sets, stats_frame))
        stats_out.append(chi(subset, categorical_features, stats_frame))

    return stats_out


def write_out(stats, i, significant, it_num):
    # output file
    out_file_name = filename + "_out_" + str(it_num) + ".csv"
    stat_file_name = filename + "_stats_" + str(it_num) + ".txt"
    heading_text = "Output: set division and statistics from run " + str(it_num + 1)
    st.subheader(heading_text)

    st.write("Input set amended with set allocation")
    st.write(input_d)
    output_csv = input_d.to_csv(index=False).encode('utf-8')
    key = "download-csv-run" + str(it_num)


    # save statistics to file if there was more than 1 set
    if no_sets > 1:
        # iterations = i + 1
        txt_content = ""
        txt_content += 'Results for comparison between new sets:\n'
        st.write('**Results for comparison between new sets:**  \n')

        if significant:
            txt_content += "  \nIn 20 iterations no split could be found that results in p>.2 for all variables.  \n  \n"
            st.write("  \nIn 20 iterations no split could be found that results in p>.2 for all variables.  \n  \n")
        output = ""
        output_st = ""
        for testgroup in stats:
            for test in testgroup:
                if len(absolute_features) > 0:
                    output += f"Absolute variable instance '{stats[stats.index(testgroup)][testgroup.index(test)][0]}': " \
                             f"{stats[stats.index(testgroup)][testgroup.index(test)][1]} for " \
                             f"'{stats[stats.index(testgroup)][testgroup.index(test)][2]}': X2(" \
                             f"{stats[stats.index(testgroup)][testgroup.index(test)][4]}) = " \
                             f"{round(stats[stats.index(testgroup)][testgroup.index(test)][3],3)}," \
                             f" p = {round(stats[stats.index(testgroup)][testgroup.index(test)][5], 3)};  \n"

                    output_st += f"Absolute variable instance '{stats[stats.index(testgroup)][testgroup.index(test)][0]}': " \
                                 f"{stats[stats.index(testgroup)][testgroup.index(test)][1]} for " \
                                 f"'{stats[stats.index(testgroup)][testgroup.index(test)][2]}': _$\u03C7^2$_(" \
                                 f"{stats[stats.index(testgroup)][testgroup.index(test)][4]}) = " \
                                 f"{round(stats[stats.index(testgroup)][testgroup.index(test)][3], 3)}," \
                                 f" _p_ = {round(stats[stats.index(testgroup)][testgroup.index(test)][5], 3)};  \n"
                else:
                    output += f"{stats[stats.index(testgroup)][testgroup.index(test)][1]} for " \
                             f"'{stats[stats.index(testgroup)][testgroup.index(test)][2]}': X2(" \
                             f"{stats[stats.index(testgroup)][testgroup.index(test)][4]}) = " \
                             f"{round(stats[stats.index(testgroup)][testgroup.index(test)][3],3)}," \
                             f" p = {round(stats[stats.index(testgroup)][testgroup.index(test)][5], 3)};  \n"
                    output_st += f"{stats[stats.index(testgroup)][testgroup.index(test)][1]} for " \
                                 f"'{stats[stats.index(testgroup)][testgroup.index(test)][2]}': _$\u03C7^2$_(" \
                                 f"{stats[stats.index(testgroup)][testgroup.index(test)][4]}) = " \
                                 f"{round(stats[stats.index(testgroup)][testgroup.index(test)][3], 3)}," \
                                 f" _p_ = {round(stats[stats.index(testgroup)][testgroup.index(test)][5], 3)};  \n"

        st.write(output_st)
        txt_content += output

        col_titles = []
        for set in range(no_sets):
            col_titles.append(f"Set {set+1}")
        col_titles.append("All")
        if len(categorical_features) > 0:
            txt_content += "  \nCross-tables for the distribution of categorical features:  \n  \n"
            st.write("  \n**Cross-tables for the distribution of categorical features:**  \n  \n")
            for feat in categorical_features:
                data_crosstab = pd.crosstab(input_d[feat],
                                       input_d['set_number'], margins=True)
                txt_content += (data_crosstab.to_string() + "\n\n")
                cross = data_crosstab.rename(columns=lambda x: 'Set ' + str(x), inplace=False)
                st.dataframe(cross, column_config={
                    "Set All": "All",
                })

        if len(absolute_features) > 0:
            txt_content += "  \nCross-table for the distribution of the absolute feature:  \n  \n"
            st.write("  \n**Cross-table for the distribution of the absolute feature:**  \n  \n")
            data_crosstab = pd.crosstab(input_d[absolute_features[0]],
                                        input_d['set_number'], margins=True)
            txt_content += (data_crosstab.to_string() + "\n\n")
            cross = data_crosstab.rename(columns=lambda x: 'Set ' + str(x), inplace=False)
            st.dataframe(cross, column_config={
                "Set All": "All",
            })

        if len(continuous_features) > 0:
            txt_content += "  \nAverage values per set:  \n  \n"
            st.write("  \n**Average values per set:**  \n  \n")
            output = ""
            for feat in continuous_features:
                for itemset in range(1, no_sets + 1):
                    mean = round(input_d.loc[input_d['set_number'] == itemset , feat].mean(),3)
                    output += feat + " in set " + str(itemset) + ": " + str(mean) + "  \n"
            st.write(output)
            txt_content += output

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for file_name, data in [
                (stat_file_name, io.StringIO(txt_content)),
                (out_file_name, io.BytesIO(output_csv))
            ]:
                zip_file.writestr(file_name, data.getvalue())

        zip_file_name= filename + "_run_" + str(it_num) + ".zip"

        st.download_button("Download statistics only", data=txt_content, file_name=stat_file_name)
        st.download_button("Download set division as .csv file", output_csv, out_file_name, "text/csv", key=key)
        st.download_button("Download .zip file with set division and statistics", mime="application/zip",
                             data=zip_buffer, file_name=zip_file_name)

@st.cache_data(experimental_allow_widgets=True)
def run_all(i, it_num, data):
    output_sets = []
    for _ in range(0, no_sets):
        output_sets.append([])

    if no_sets > 1:
        # prepare data
        dat = prepare_data(data, continuous_features, categorical_features, label, disregard)

        # split by "absolute" feature and remove absolute features from clustering
        if len(absolute_features) == 1:
            datasets = split(absolute_features[0], dat)
        else:
            datasets = [dat]
    else:
        print("Please use more than 1 set for this tool to be meaningful!")
        sys.exit(1)  # abort

    # for each part of the absolute splitting make sets
    for data in datasets:
        # form clusters
        clusters = clustering(data, categorical_features, continuous_features)

        # divide in sets
        divide_in_sets(clusters, output_sets)

    set_numbers = []
    for item in input_d.index:
        for j, _ in enumerate(output_sets):
            if item in output_sets[j]:
                set_numbers.append(j + 1)

    # add new column
    input_d['set_number'] = set_numbers

    # do statistics
    stats = statistics(input_d)

    # This checks for looping but is inside the loop
    all_ns = True

    for var_type in stats:
        for var in var_type:
            if var[5] < 0.2:
                all_ns = False

    # write to files
    if all_ns:
        write_out(stats, i, False, it_num)
    elif i < 19:
        i = i + 1
        run_all(i, it_num, input_d)
    else:
        print("\nCouldn't split into sets as expected. The output might be less than optimal, please run again for "
              "better results")
        write_out(stats, i, True, it_num)


### build interface and actually run the program ###

col1, col2 = st.columns([1,3])
col2.title('Discuit')
image = Image.open('discuit-logo.png')
col1.image(image)
df = pd.read_csv("example.csv")


st.write("To start please upload a file containing the data set that needs to be split. You can find information on "
         "the further steps on the left-hand side.")
with st.expander("Show an example of the correct formatting of your .csv file"):
    example = st.dataframe(df, hide_index=True)

col3, col4 = st.sidebar.columns([1,3])
col3.image(image)
col4.title('Discuit')

st.sidebar.markdown(
"""
**Reference:**  \n
Please cite this app when using it as follows:  \n
De Kok, D. (2023). _Discuit App [Computer software]_. https://doi.org/10.5281/zenodo.8195515

**Steps to take:**
- Upload an input file (.csv) with your items;
""")

col5, col6 = st.sidebar.columns([1,6])
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
        if st.checkbox('Show input data', value= True, key="raw_data"):
            st.subheader('Input data')
            st.write(input_d)

        st.subheader("Set your parameters")
        col1, col2 = st.columns([1, 1])
        set_help = "Please select the number of matched sets you need."
        no_sets = col2.slider("Number of output sets", value=2, step=1, min_value=2, max_value=20, key="sets", help=set_help)

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
        iterations = col2.slider("Number of splits", value=1, step=1, min_value=1, max_value=20, key="iterations", help=it_help)

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
                    for it_num in range(iterations):
                        st.write("Making sets... run: ", it_num+1, " from ", iterations)
                        # initiate loop-tracking
                        i = 0
                        # start first loop
                        run_all(i, it_num, input_d)
                        key = "clear_Button" + str(it_num)
                        x.button("Clear results", on_click=clear_button, disabled=False, key=key)
            else:
                st.write(":red[Please define all variable types!]")
