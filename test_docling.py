import json
import logging
from pathlib import Path
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

options = PdfPipelineOptions()
options.generate_picture_images = True
converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})

try:
    result = converter.convert("/kaggle/input/textbooks/How Many (Addition and Subtraction of Single Digit Numbers).pdf")
    doc_obj = result.document
    print("Found pictures:", len(doc_obj.pictures) if hasattr(doc_obj, 'pictures') else 0)
    if hasattr(doc_obj, 'pictures') and doc_obj.pictures:
        pic = next(iter(doc_obj.pictures))
        print("Picture type:", type(pic))
        print("Attributes:", dir(pic))
        if hasattr(pic, 'image'):
            print("Image type:", type(pic.image))
            print("Image attributes:", dir(pic.image))
        if hasattr(pic, 'get_image'):
            print("Has get_image")
except Exception as e:
    print("Error:", e)
