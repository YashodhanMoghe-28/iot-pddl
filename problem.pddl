
(define (problem industrial-instance)

 (:domain industrial-monitor)

 (:objects
    zone1 - zone
 )

 (:init
    
 )

 (:goal
    (and
        (not (fan-on zone1)) (not (buzzer-on zone1)) (not (occupancy-led-on zone1)) (not (noise-warning-on zone1)) (not (door-alert-on zone1))
    )
 )

)
