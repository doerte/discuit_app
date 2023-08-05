import io
import zipfile
import streamlit as st


def write_to_streamlit(output, no_sets):
    i = 0
    for r in output.runs:
        i = i + 1
        heading_text = "Output: set division and statistics from run " + str(i)
        st.subheader(heading_text)

        # show dataframe
        st.write("Input set amended with set allocation")
        st.write(r.dataframe)

        # save .csv
        output_csv = r.dataframe.to_csv(index=False).encode('utf-8')
        key = "download-csv-run" + str(i)

        # save stats output
        txt_content = ""
        txt_content += f'Number of iterations: {r.no_it + 1} \n \nResults for comparison between new sets:\n'

        st.write('Number of iterations ran:', r.no_it + 1)
        st.write('**Results for comparison between new sets:**  \n')

        if r.significant:
            txt_content += "\nIn 20 iterations no split could be found that results in p>.2 for all variables.\n\n"
            st.write("  \nIn 20 iterations no split could be found that results in p>.2 for all variables.  \n  \n")

        st_content = ""
        for test in r.result:
            # TODO: find a way to only include the first part if there is an absolute variable
            txt_content += f"Absolute variable instance '{test.identifier}': {test.test} for '{test.feature}': " \
                           f"X2({test.df}) = {test.x2}, p = {test.p}\n"
            st_content += (f"Absolute variable instance '{test.identifier}': {test.test} for '{test.feature}': "
                           f"_$\u03C7 ^ 2$_({test.df}) = {test.x2}, p = {test.p}  \n")

        st.write(st_content)

        col_titles = []
        for subset in range(no_sets):
            col_titles.append(f"Set {subset + 1}")
        col_titles.append("All")

        if r.tables[0].crosstab is not None:
            txt_content += "  \nCross-tables for the distribution of categorical and absolute variables:  \n  \n"
            st.write("  \n**Cross-tables for the distribution of categorical and absolute variables:**  \n  \n")

            for table in r.tables:
                txt_content += (table.crosstab.to_string() + "\n\n")
                cross = table.crosstab.rename(columns=lambda x: 'Set ' + str(x), inplace=False)
                st.dataframe(cross, column_config={
                    "Set All": "All",
                })

        if r.averages is not None:
            txt_content += "\nAverage values per set:\n\n"
            st.write("  \n**Average values per set:**  \n  \n")

            output = ""
            for average in r.averages:
                output += (average.feature + " in set " + str(average.set_no) + ": " + str(average.mean)
                           + "  \n")
            st.write(output)
            txt_content += output

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for file_name, data in [
                (r.txt_name, io.StringIO(txt_content)),
                (r.csv_name, io.BytesIO(output_csv))
            ]:
                zip_file.writestr(file_name, data.getvalue())

        zip_file_name = r.filename + "_run_" + str(r.no_it) + ".zip"

        st.download_button("Download statistics only", data=txt_content, file_name=r.txt_name)
        st.download_button("Download set division as .csv file", output_csv, r.csv_name, "text/csv", key=key)
        st.download_button("Download .zip file with set division and statistics", mime="application/zip",
                           data=zip_buffer, file_name=zip_file_name)
