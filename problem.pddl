
(define (problem industrial-instance)

 (:domain industrial-monitor)

 (:objects
    zone1 - zone
 )

 (:init
    (occupied zone1) (occupancy-led-on zone1)
 )

 (:goal
    (and
        (not (fan-on zone1)) (not (buzzer-on zone1)) (occupancy-led-on zone1) (not (noise-warning-on zone1)) (not (door-alert-on zone1))
    )
 )

)
