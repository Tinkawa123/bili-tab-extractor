import cv2, numpy as np
img = cv2.imread(r"out/stills/still_044.40.png").astype(np.int16)
# rows 03 and 04 bands (from full frame coords): row03 y ~ 560-660, row04 y ~ 690-780
r3 = img[560:655, 700:1290]
r4 = img[690:785, 700:1290]
print("row3 vs row4 mean abs diff:", np.abs(r3-r4).mean())
# also row02 vs row03
r2 = img[430:520, 700:1290]
print("row2 vs row3 mean abs diff:", np.abs(r2-img[560:650,700:1290]).mean())
# row01 vs row02 shifted
r1 = img[300:400, 700:1290]
print("row1 vs row2 mean abs diff:", np.abs(r1-img[430:530,700:1290]).mean())
