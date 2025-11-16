import cv2
import pytesseract
from pytesseract import Output
from PIL import Image
import pyautogui

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

screenshot = pyautogui.screenshot()
screenshot.save("screenshot.png")

def ocr_with_boxes(input_path, output_path):
    img = cv2.imread(input_path)
    data = pytesseract.image_to_data(img, lang="eng", output_type=Output.DICT)

    n_boxes = len(data['text'])
    for i in range(n_boxes):
        text = data['text'][i]
        conf = int(data['conf'][i])

        if text.strip() != "" and conf > 0:
            x = data['left'][i]
            y = data['top'][i]
            w = data['width'][i]
            h = data['height'][i]

            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(img, text, (x, y - 5),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    cv2.imwrite(output_path, img)
    return data

data = ocr_with_boxes("screenshot.png", "screenshot_boxes.png")
print("\n".join([t for t in data['text'] if t.strip() != ""]))
