#!/usr/bin/python
import sys
import rospy
import smach
import smach_ros

from std_msgs.msg import String

# import of generic states
import mir_states.common.manipulation_states as gms

# for dynamic reconfigure node + grasp monitor
import mcr_states.common.basic_states as gbs
# action lib
from smach_ros import ActionServerWrapper


# action lib
from smach_ros import ActionServerWrapper
from mir_yb_action_msgs.msg import InsertObjectAction
from mir_yb_action_msgs.msg import InsertObjectFeedback
from mir_yb_action_msgs.msg import InsertObjectResult

#===============================================================================
class SetupMoveArm(smach.State): # inherit from the State base class
    def __init__(self, arm_target):
        smach.State.__init__(self, outcomes=['succeeded'],
                                   input_keys=['insert_object_goal'],
                                   output_keys=['insert_object_feedback', 'insert_object_result', 'move_arm_to'])
        self.counter = 0
        self.arm_target = arm_target

    def execute(self, userdata):
        # updating result (false until finished all actions)
        result = InsertObjectResult()
        result.success = False
        userdata.insert_object_result = result
        # get arm goal from actionlib
        platform = userdata.insert_object_goal.robot_platform
        # giving feedback to the user
        feedback = InsertObjectFeedback()
        feedback.current_state = 'MOVE_ARM'
        if self.arm_target == 'pre':
            platform = platform + "_pre"
        feedback.text='[insert_object] Moving the arm to ' + platform
        userdata.move_arm_to = platform
        userdata.insert_object_feedback = feedback
        return 'succeeded'
#===============================================================================

class SetActionLibResult(smach.State):
    def __init__(self, result):
        smach.State.__init__(self,  outcomes=['succeeded'],
                                    input_keys=['insert_object_goal'],
                                    output_keys=['insert_object_feedback', 'insert_object_result'])
        self.result = result

    def execute(self, userdata):
        result = InsertObjectResult()
        result.success = self.result
        userdata.insert_object_result = result
        return 'succeeded'

#===============================================================================

class send_event(smach.State):
    '''
    This class publishes e_start on topic_name argument
    '''
    def __init__(self, topic_name, event):
        smach.State.__init__(self,  outcomes=['success'],
                                    input_keys=['insert_object_goal'],
                                    output_keys=['insert_object_feedback', 'insert_object_result'])
        # create publisher
        self.topic_name = topic_name
        self.event = event
        self.publisher = rospy.Publisher(self.topic_name, String, queue_size=10)
        # giving some time to the publisher to register in ros network
        rospy.sleep(0.1)

    def execute(self, userdata):
        # give feedback
        feedback = InsertObjectFeedback()
        feedback.current_state = 'SEND_EVENT'
        userdata.insert_object_feedback = feedback
        # creating string message
        msg = String()
        # filling message
        msg.data = self.event
        # publish
        self.publisher.publish(msg)
        rospy.loginfo('publishing on ' + self.topic_name + ' ' + self.event)
        # wait, dont kill the node so quickly
        rospy.sleep(0.2)
        return 'success'
        
#===============================================================================

class wait_for_event(smach.State):
    '''
    This state will take a event name as input and waits for the event to
    be published.
    '''
    def __init__(self, topic_name, timeout_duration):
        smach.State.__init__(self,  outcomes=['success', 'failure', 'timeout'],
                                    input_keys=['insert_object_goal'],
                                    output_keys=['insert_object_feedback', 'insert_object_result'])
        rospy.Subscriber(topic_name, String, self.event_cb)
        self.callback_msg_ = None
        self.message_received = False
        self.timeout = rospy.Duration.from_sec(timeout_duration)

    def event_cb(self, callback_msg):
        self.callback_msg_ = callback_msg
        self.message_received = True

    def getResult(self):
        if self.callback_msg_ is None:
            rospy.logerr('event out message not received in the specified time')
            return 'timeout'
        elif self.callback_msg_.data == 'e_failure':
            self.callback_msg_ = None
            return 'failure'
        elif self.callback_msg_.data == 'e_success' or self.callback_msg_.data == 'e_selected':
            self.callback_msg_ = None
            return 'success'
        else:
            print('[wait for event] : no response, or response message "{}" is not known.'.format(self.callback_msg_.data))
            self.callback_msg_ = None
            return 'failure'
        
    def execute(self, userdata):
        # give feedback
        feedback = InsertObjectFeedback()
        feedback.current_state = 'WAIT_FOR_FEEDBACK'
        userdata.insert_object_feedback = feedback
        # reset flag of received to false
        print "waiting for node response..."
        self.message_received = False
        start_time = rospy.Time.now()
        rate = rospy.Rate(10) # 10hz
        # wait for message to arrive
        while((rospy.Time.now() - start_time < self.timeout) and not(self.message_received) and not(rospy.is_shutdown())):
            rate.sleep()
        # dont kill the node so quickly, wait for handshake of nodes
        print("(rospy.Time.now() - start_time < self.timeout) = {}".format((rospy.Time.now() - start_time < self.timeout)))
        print("self.message_received = {}".format((self.message_received)))
        rospy.sleep(0.2)  
        return self.getResult()

        
#===============================================================================
#===============================================================================

def main():
    rospy.init_node('insert_wheel_in_axis_server')
    # Construct state machine
    sm = smach.StateMachine(
            outcomes=['OVERALL_SUCCESS','OVERALL_FAILED'],
            input_keys = ['insert_object_goal'],
            output_keys = ['insert_object_feedback', 'insert_object_result'])
    with sm:
        smach.StateMachine.add('PUBLISH_REFERENCE_FRAME', gbs.send_event([('/static_transform_publisher_node/event_in', 'e_start')]),
                transitions={'success':'GET_AXIS_POSE'})

        smach.StateMachine.add('GET_AXIS_POSE', gbs.send_and_wait_events_combined(
                event_in_list=[('/mcr_perception/car_wheel_axis_detector/input/event_in','e_trigger')],
                event_out_list=[('/mcr_perception/car_wheel_axis_detector/output/event_out','e_done', True)],
                timeout_duration=10),
                transitions={'success':'SHIFT_AXIS_POSE',
                            'timeout':'SET_ACTION_LIB_FAILURE',
                            'failure':'SET_ACTION_LIB_FAILURE'})

        smach.StateMachine.add('SHIFT_AXIS_POSE', gbs.send_and_wait_events_combined(
                                    event_in_list=[('/wheel_axis_pose_shifter/event_in','e_start')],
                                    event_out_list=[('/wheel_axis_pose_shifter/event_out','e_success', True)],
                                    timeout_duration=5),
                transitions={'success':'PLAN_WHOLE_BODY_MOTION',
                             'timeout':'SET_ACTION_LIB_FAILURE',
                             'failure':'SET_ACTION_LIB_FAILURE'})

        smach.StateMachine.add('PLAN_WHOLE_BODY_MOTION', send_event('/whole_body_motion_calculator_pipeline/event_in','e_start'),
            transitions={'success':'WAIT_PLAN_WHOLE_BODY_MOTION'})

        # wait for the result of the pregrasp planner
        smach.StateMachine.add('WAIT_PLAN_WHOLE_BODY_MOTION', wait_for_event('/whole_body_motion_calculator_pipeline/event_out', 15.0),
            transitions={'success':'CALCULATE_BASE_MOTION',
                          'timeout': 'STOP_PLAN_WHOLE_BODY_MOTION_WITH_FAILURE',
                          'failure':'STOP_PLAN_WHOLE_BODY_MOTION_WITH_FAILURE'})
        
        # pregrasp planner failed or timeout, stop the component and then return overall failure
        smach.StateMachine.add('STOP_PLAN_WHOLE_BODY_MOTION_WITH_FAILURE', send_event('/whole_body_motion_calculator_pipeline/event_in','e_stop'),
            transitions={'success':'PLAN_ARM_MOTION'})  # go to  select pose input and plan arm motion

        smach.StateMachine.add('CALCULATE_BASE_MOTION', gbs.send_and_wait_events_combined(
                event_in_list=[('/base_motion_calculator/event_in','e_start')],
                event_out_list=[('/base_motion_calculator/event_out','e_success', True)],
                timeout_duration=5),
                transitions={'success':'STOP_PLAN_WHOLE_BODY_MOTION',
                             'timeout':'STOP_MOVE_BASE_TO_OBJECT',
                             'failure':'STOP_MOVE_BASE_TO_OBJECT'})

        # wbc pipeline  was successful, so lets stop it since its work is done
        smach.StateMachine.add('STOP_PLAN_WHOLE_BODY_MOTION', send_event('/whole_body_motion_calculator_pipeline/event_in','e_stop'),
            transitions={'success':'SETUP_MOVE_ARM_PRE_STAGE'})

        ############################################### unstage start ########################################
        smach.StateMachine.add('SETUP_MOVE_ARM_PRE_STAGE', SetupMoveArm('pre'),
                transitions={'succeeded': 'MOVE_ARM_PRE_STAGE'})

        smach.StateMachine.add('MOVE_ARM_PRE_STAGE', gms.move_arm(),
                transitions={'succeeded': 'OPEN_GRIPPER_TO_GRASP',
                             'failed': 'MOVE_ARM_PRE_STAGE'})

        smach.StateMachine.add('OPEN_GRIPPER_TO_GRASP', gms.control_gripper('open'),
                transitions={'succeeded': 'SETUP_MOVE_ARM_STAGE'})

        smach.StateMachine.add('SETUP_MOVE_ARM_STAGE', SetupMoveArm('final'),
                transitions={'succeeded': 'MOVE_ARM_STAGE'})

        smach.StateMachine.add('MOVE_ARM_STAGE', gms.move_arm(),
                transitions={'succeeded': 'CLOSE_GRIPPER',
                             'failed': 'MOVE_ARM_STAGE'})

        smach.StateMachine.add('CLOSE_GRIPPER', gms.control_gripper('close'),
                transitions={'succeeded': 'SETUP_MOVE_ARM_PRE_STAGE_AGAIN'})

        smach.StateMachine.add('SETUP_MOVE_ARM_PRE_STAGE_AGAIN', SetupMoveArm('pre'),
                transitions={'succeeded': 'MOVE_ARM_PRE_STAGE_AGAIN'})

        smach.StateMachine.add('MOVE_ARM_PRE_STAGE_AGAIN', gms.move_arm(),
                transitions={'succeeded': 'MOVE_ARM_TO_HOLD_1',
                             'failed': 'MOVE_ARM_PRE_STAGE_AGAIN'})

        smach.StateMachine.add('MOVE_ARM_TO_HOLD_1', gms.move_arm("look_at_turntable"),
                               transitions={'succeeded':'MOVE_ROBOT_TO_OBJECT',
                                            'failed':'MOVE_ARM_TO_HOLD_1'})
        ############################################### unstage end ########################################

        # execute robot motion
        smach.StateMachine.add('MOVE_ROBOT_TO_OBJECT', gbs.send_and_wait_events_combined(
                event_in_list=[ ('/wbc/mcr_navigation/direct_base_controller/coordinator/event_in','e_start')],
                event_out_list=[('/wbc/mcr_navigation/direct_base_controller/coordinator/event_out','e_success', True)],
                timeout_duration=5),
                transitions={'success':'STOP_MOVE_BASE_TO_OBJECT',
                             'timeout':'STOP_MOVE_ROBOT_TO_OBJECT_WITH_FAILURE',
                             'failure':'STOP_MOVE_ROBOT_TO_OBJECT_WITH_FAILURE'})

        # send stop event_in to arm motion component
        smach.StateMachine.add('STOP_MOVE_BASE_TO_OBJECT',
                        gbs.send_event([('/wbc/mcr_navigation/direct_base_controller/coordinator/event_in','e_stop')]),
            transitions={'success':'PLAN_ARM_MOTION'})

        # send stop event_in to arm motion component and return failure
        smach.StateMachine.add('STOP_MOVE_ROBOT_TO_OBJECT_WITH_FAILURE',
                        gbs.send_event([('/wbc/mcr_navigation/direct_base_controller/coordinator/event_in','e_stop')]),
            transitions={'success':'PLAN_ARM_MOTION'})

       ########################################## PREGRASP PIPELINE 2 ##################################################

        smach.StateMachine.add('PLAN_ARM_MOTION', gbs.send_and_wait_events_combined(
                event_in_list=[('/pregrasp_planner_pipeline/event_in','e_start')],
                event_out_list=[('/pregrasp_planner_pipeline/event_out','e_success', True)],
                timeout_duration=15),
                transitions={'success':'STOP_PLAN_ARM_MOTION',
                             'timeout':'STOP_MOVE_ARM_TO_OBJECT_WITH_FAILURE_2',
                             'failure':'STOP_MOVE_ARM_TO_OBJECT_WITH_FAILURE_2'})

        smach.StateMachine.add('STOP_PLAN_ARM_MOTION', gbs.send_event([('/pregrasp_planner_pipeline/event_in','e_stop')]),
            transitions={'success':'MOVE_ARM_TO_OBJECT'})

        # execute robot motion
        smach.StateMachine.add('MOVE_ARM_TO_OBJECT', gbs.send_and_wait_events_combined(
                event_in_list=[('/waypoint_trajectory_generation/event_in','e_start')],
                event_out_list=[('/waypoint_trajectory_generation/event_out','e_success', True)],
                timeout_duration=10),
                transitions={'success':'STOP_MOVE_ARM_TO_OBJECT_2',
                             'timeout':'STOP_MOVE_ARM_TO_OBJECT_WITH_FAILURE_2',
                             'failure':'STOP_MOVE_ARM_TO_OBJECT_WITH_FAILURE_2'})

        smach.StateMachine.add('STOP_MOVE_ARM_TO_OBJECT_2', gbs.send_event([('/waypoint_trajectory_generation/event_out','e_stop')]),
            transitions={'success':'STOP_LINEAR_COMPONENTS_1'})

        #smach.StateMachine.add('STOP_MOVE_ARM_TO_OBJECTH_FAILURE', send_event('/move_arm_planned/event_in','e_stop'),
        smach.StateMachine.add('STOP_MOVE_ARM_TO_OBJECT_WITH_FAILURE_2', gbs.send_event([('/waypoint_trajectory_generation/event_out','e_stop')]),
            transitions={'success':'SET_ACTION_LIB_FAILURE'})

       ########################################## LINEAR MOTION PIPELINE ##################################################
        smach.StateMachine.add('STOP_LINEAR_COMPONENTS_1', gbs.send_event([('/poses_to_move/event_in','e_stop'),
                                                                           ('/cartesian_controller_demo/event_in', 'e_stop')]),
            transitions={'success':'PLAN_LINEAR_APPROACH'})

        smach.StateMachine.add('PLAN_LINEAR_APPROACH', gbs.send_and_wait_events_combined(
            event_in_list=[('/poses_to_move/event_in','e_start')],
            event_out_list=[('/poses_to_move/event_out','e_success', True)],
            timeout_duration=10),
            transitions={'success':'MOVE_ARM_LINEAR',
                         'timeout':'SET_ACTION_LIB_FAILURE',
                         'failure':'SET_ACTION_LIB_FAILURE'})

        smach.StateMachine.add('MOVE_ARM_LINEAR', gbs.send_and_wait_events_combined(
                event_in_list=[('/cartesian_controller_demo/event_in','e_start')],
                event_out_list=[('/cartesian_controller_demo/event_out','e_success', True)],
                timeout_duration=10),
                transitions={'success':'STOP_LINEAR_COMPONENTS_2',
                             'timeout':'STOP_LINEAR_COMPONENTS_2',
                             'failure':'STOP_LINEAR_COMPONENTS_2'})

        smach.StateMachine.add('STOP_LINEAR_COMPONENTS_2', gbs.send_event([('/poses_to_move/event_in','e_stop'),
                                                                           ('/cartesian_controller_demo/event_in', 'e_stop')]),
            transitions={'success':'OPEN_GRIPPER'})

       ########################################## LINEAR MOTION PIPELINE END ##################################################

        # close gripper
        smach.StateMachine.add('OPEN_GRIPPER', gms.control_gripper('open'),
                transitions={'succeeded': 'MOVE_ARM_TO_HOLD'})

        # move arm to HOLD position
        smach.StateMachine.add('MOVE_ARM_TO_HOLD', gms.move_arm("look_at_turntable"),
                               transitions={'succeeded':'SET_ACTION_LIB_SUCCESS',
                                            'failed':'MOVE_ARM_TO_HOLD'})

        # set action lib result
        smach.StateMachine.add('SET_ACTION_LIB_SUCCESS', SetActionLibResult(True),
                                transitions={'succeeded':'OVERALL_SUCCESS'})

        # set action lib result
        smach.StateMachine.add('SET_ACTION_LIB_FAILURE', SetActionLibResult(False),
                               transitions={'succeeded':'MOVE_ARM_TO_HOLD_FAILURE'})

        smach.StateMachine.add('MOVE_ARM_TO_HOLD_FAILURE', gms.move_arm("look_at_turntable"),
                               transitions={'succeeded':'OVERALL_FAILED',
                                            'failed':'MOVE_ARM_TO_HOLD_FAILURE'})

    # smach viewer
    sis = smach_ros.IntrospectionServer('insert_wheel_smach_viewer', sm, '/INSERT_WHEEL_IN_AXIS_SMACH_VIEWER')
    sis.start()

    # Construct action server wrapper
    asw = ActionServerWrapper(
        server_name = 'insert_wheel_in_axis_server',
        action_spec = InsertObjectAction,
        wrapped_container = sm,
        succeeded_outcomes = ['OVERALL_SUCCESS'],
        aborted_outcomes   = ['OVERALL_FAILED'],
        preempted_outcomes = ['PREEMPTED'],
        goal_key     = 'insert_object_goal',
        feedback_key = 'insert_object_feedback',
        result_key   = 'insert_object_result')
    # Run the server in a background thread
    asw.run_server()
    rospy.spin()

if __name__ == '__main__':
    main()

