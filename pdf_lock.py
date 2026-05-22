from flask import Flask, render_template_string, request, send_file
from PyPDF2 import PdfReader, PdfWriter
import os

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>PDF Locker</title>
    <style>
        body{
            font-family: Arial;
            text-align:center;
            margin-top:50px;
            background:#f2f2f2;
        }
        .box{
            background:white;
            padding:30px;
            width:350px;
            margin:auto;
            border-radius:10px;
            box-shadow:0 0 10px rgba(0,0,0,0.2);
        }
        input{
            width:90%;
            padding:10px;
            margin:10px;
        }
        button{
            padding:10px 20px;
            background:#007bff;
            color:white;
            border:none;
            border-radius:5px;
            cursor:pointer;
        }
    </style>
</head>
<body>

<div class="box">
    <h2>PDF Locker</h2>

    <form method="POST" enctype="multipart/form-data">
        <input type="file" name="pdf" required><br>
        <input type="password" name="password" placeholder="Enter Password" required><br>
        <button type="submit">Lock PDF</button>
    </form>
</div>

</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def home():

    if request.method == "POST":

        pdf = request.files["pdf"]
        password = request.form["password"]

        input_path = "input.pdf"
        output_path = "locked.pdf"

        pdf.save(input_path)

        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        writer.encrypt(password)

        with open(output_path, "wb") as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True)

    return render_template_string(HTML)

if __name__ == "__main__":
    app.run()
print(f"\nLocked PDF saved as:\n{output_pdf}")
