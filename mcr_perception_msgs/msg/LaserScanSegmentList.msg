Header header					#  sequence ID: consecutively increasing ID 
								## uint32 seq
								#  Two-integer timestamp that is expressed as:
								#  * stamp.secs: seconds (stamp_secs) since epoch
								#  * stamp.nsecs: nanoseconds since stamp_secs
								#  time-handling sugar is provided by the client library
								## time stamp
								#  Frame this data is associated with
								#  0: no frame
								#  1: global frame
								## string frame_id
	
uint32 num_segments				# number of segments

LaserScanSegment[] segments			# list of detected person
