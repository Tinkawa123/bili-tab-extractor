import cv2, numpy as np
img = cv2.imread(r"out/stills/still_044.40.png")
# crop paper rows area
c = img[280:800, 660:1320]
c = cv2.resize(c, None, fx=2.2, fy=2.2, interpolation=cv2.INTER_CUBIC)
cv2.imwrite(r"out/stills/zoom_444_paper.png", c)
c2 = img[150:260, 660:1420]
c2 = cv2.resize(c2, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
cv2.imwrite(r"out/stills/zoom_444_head.png", c2)
img3 = cv2.imread(r"out/stills/still_030.50.png")
c3 = img3[280:350, 540:1000]
c3 = cv2.resize(c3, None, fx=4.0, fy=4.0, interpolation=cv2.INTER_CUBIC)
cv2.imwrite(r"out/stills/zoom_305_nav.png", c3)
print("ok")
