/*
 * Copyright [2017] <Bonn-Rhein-Sieg University>
 *
 * Author: Torsten Jandt
 *
 */

#pragma once

#include <ros/ros.h>
#include <vector>
#include <string>
#include <mir_planner_executor_msgs/ReAddGoals.h>
#include <rosplan_knowledge_msgs/KnowledgeItem.h>

class KnowledgeUpdater {
private:
    static constexpr const char* LOG_NAME = "KNOWLEDGE_UPDATER";

    ros::ServiceClient rosplan_update_client_;
    ros::ServiceClient rosplan_get_goals_client_;
    ros::ServiceClient rosplan_get_knowledge_client_;

    std::vector<rosplan_knowledge_msgs::KnowledgeItem> removed_goals_;
    ros::ServiceServer re_add_goals_server_;

    std::string toUpper(std::string str);
    bool update_knowledge(uint8_t type, std::string name, std::vector<std::pair<std::string, std::string>> values);

public:
    KnowledgeUpdater(ros::NodeHandle &nh);
    ~KnowledgeUpdater();
    bool addGoal(std::string name, std::vector<std::pair<std::string, std::string>> values);
    bool remGoal(std::string name, std::vector<std::pair<std::string, std::string>> values);
    bool addKnowledge(std::string name, std::vector<std::pair<std::string, std::string>> values);
    bool remKnowledge(std::string name, std::vector<std::pair<std::string, std::string>> values);
    bool remGoalsWithObject(std::string object_name);
    bool remGoalsWithLocation(std::string location);
    bool remGoalsRelatedToLocation(std::string location);
    bool re_add_goals(mir_planner_executor_msgs::ReAddGoals::Request &req, mir_planner_executor_msgs::ReAddGoals::Response &res);
};
