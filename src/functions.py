import numpy as np
import cv2
from tf_model_person_detection import Model 

def calculate_distance(point1, point2):
    '''Calculate usual distance.'''
    x1, y1 = point1
    x2, y2 = point2
    return np.linalg.norm([x1 - x2, y1 - y2])

def convert_to_bird(centers, M):
    '''Apply the perpective to the bird's-eye view.'''
    centers = [cv2.perspectiveTransform(np.float32([[center]]), M) for center in centers.copy()]
    centers = [list(center[0, 0]) for center in centers.copy()]
    return centers

def bird_detect_people_on_frame(img, confidence, distance, width, height,
                                model, region=None, dst=None):
    results = model.predict_real([img[:, :, ::-1]])
    xyxy = results.xyxy[0].cpu().numpy()  # xyxy are the box coordinates
    #          x1 (pixels)  y1 (pixels)  x2 (pixels)  y2 (pixels)   confidence        class
    # tensor([[7.47613e+02, 4.01168e+01, 1.14978e+03, 7.12016e+02, 8.71210e-01, 0.00000e+00],
    #         [1.17464e+02, 1.96875e+02, 1.00145e+03, 7.11802e+02, 8.08795e-01, 0.00000e+00],
    #         [4.23969e+02, 4.30401e+02, 5.16833e+02, 7.20000e+02, 7.77376e-01, 2.70000e+01],
    #         [9.81310e+02, 3.10712e+02, 1.03111e+03, 4.19273e+02, 2.86850e-01, 2.70000e+01]])

    xyxy = xyxy[xyxy[:, 4] >= confidence]  # Filter desired confidence
    xyxy = xyxy[:, :4]

    # Calculate the centers of the circles
    # They will be the centers of the bottom of the boxes
    centers = []
    for x1, y1, x2, y2 in xyxy:
        center = [np.mean([x1, x2]), y2]
        centers.append(center)


    # We create two transformations
    if region is None:
        # The region on the original image
        region = np.float32([[144, 130], [222, 129], [width, height], [0, height]])
    if dst is None:
        # The rectangle we want the image to be trasnformed to
        dst = np.float32([[0, 0], [width, 0], [width, 3*width], [0, 3*width]])
    # The first transformation is straightforward: the region to the rectangle
    # as thin the example before
    M = cv2.getPerspectiveTransform(region, dst)

    # The second transformation is a trick, because, using the common transformation,
    # we can't draw circles at left of the region.
    # This way, we flip all things and draw the circle at right of the region,
    # because we can do it.
    region_flip = region*np.float32([-1, 1]) + np.float32([width, 0])
    dst_flip = dst*np.float32([-1, 1]) + np.float32([width, 0])
    M_flip = cv2.getPerspectiveTransform(region_flip, dst_flip)

    # Convert to bird
    # Now, the center of the circles will be positioned on the rectangle
    # and we can calculate the usual distance
    bird_centers = convert_to_bird(centers, M)

    # We verify if the circles colide
    # If so, they will be red
    colors = ['green']*len(bird_centers)
    for i in range(len(bird_centers)):
        for j in range(i+1, len(bird_centers)):
            dist = calculate_distance(bird_centers[i], bird_centers[j])
            if dist < distance:
                colors[i] = 'red'
                colors[j] = 'red'

    # We draw the circles
    # Because we have two transformation, we will start with two empty
    # images ("overlay" images) to draw the circles
    overlay = np.zeros((3*width, 4*width, 3), np.uint8)
    overlay_flip = np.zeros((3*width, 4*width, 3), np.uint8)
    for i, bird_center in enumerate(bird_centers):
        if colors[i] == 'green':
            color = (0, 255, 0)
        else:
            color = (0, 0, 255)
        x, y = bird_center
        x = int(x)
        y = int(y)
        if x >= int(distance/2+15/2):
            # If it's the case the circle is inside or at right of our region
            # we can use the normal overlay image
            overlay = cv2.circle(overlay, (x, y), int(distance/2),
                                  color, 15, lineType=cv2.LINE_AA)
        else:
            # If the circle is at left of the region,
            # we draw the circle inverted on the other overlay image
            x = width - x
            overlay_flip = cv2.circle(overlay_flip, (x, y), int(distance/2),
                                  color, 15, lineType=cv2.LINE_AA)

    # We apply the inverse transformation to the overlay
    overlay = cv2.warpPerspective(overlay, M, (width, height),
                                  cv2.INTER_NEAREST, cv2.WARP_INVERSE_MAP)
    # We apply the inverse of the other transformation to the other overlay
    overlay_flip = cv2.warpPerspective(overlay_flip, M_flip, (width, height),
                                       cv2.INTER_NEAREST, cv2.WARP_INVERSE_MAP)
    # Now we "unflip" what the second overlay
    overlay_flip = cv2.flip(overlay_flip, 1)

    # We add all images
    img = cv2.addWeighted(img, 1, overlay, 1, 0)
    img = cv2.addWeighted(img, 1, overlay_flip, 1, 0)

    return img