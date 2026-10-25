package com.ruoyi.taglibrary.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;

/** 智能体运行后台同步（不依赖浏览器轮询）。 */
@Configuration
@EnableScheduling
public class TsAgentSchedulingConfig {
}
