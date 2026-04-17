from ultralytics import YOLO
import cv2

# Load models
custom_model = YOLO("runs/detect/train/weights/best.pt")  # your trained model
coco_model = YOLO("yolov8n.pt")  # default model for people & vehicles

cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    alert = "System Normal"

    # ---------- CUSTOM MODEL ----------
    custom_results = custom_model(frame, conf=0.25)[0]

    for box in custom_results.boxes:
        cls = int(box.cls[0])
        label = custom_model.names[cls]

        if label == "fire":
            alert = "🔥 Fire Detected → Fire Department"

        elif label == "garbage":
            alert = "🗑️ Garbage Detected → Municipality"

        elif label == "fall":
            alert = "🚑 Medical Emergency → Ambulance"

        elif label == "accident":
            alert = "🚨 Accident Detected → Police"

    # ---------- COCO MODEL ----------
    coco_results = coco_model(frame, conf=0.3)[0]

    people_count = 0
    vehicle_count = 0

    for box in coco_results.boxes:
        cls = int(box.cls[0])

        # person class
        if cls == 0:
            people_count += 1

        # vehicle classes
        if cls in [2, 3, 5, 7]:  # car, bike, bus, truck
            vehicle_count += 1

    # Crowd detection
    if people_count > 4:
        alert = "👥 Overcrowding → Police"

    # Traffic detection
    if vehicle_count > 5:
        alert = "🚗 Traffic Congestion → Police"

    # ---------- DISPLAY ----------
    annotated_frame = coco_results.plot()  # shows people + vehicles
    annotated_frame = custom_results.plot(img=annotated_frame)  # overlay your model

    cv2.putText(annotated_frame, f"People: {people_count}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    cv2.putText(annotated_frame, f"Vehicles: {vehicle_count}", (10, 70),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

    cv2.putText(annotated_frame, f"ALERT: {alert}", (10, 120),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

    cv2.imshow("AI Surveillance System", annotated_frame)

    if cv2.waitKey(1) == 27:
        break

cap.release()
cv2.destroyAllWindows()
