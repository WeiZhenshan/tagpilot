package com.ruoyi.taglibrary.service.impl;

import java.util.HashSet;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import com.ruoyi.common.core.domain.entity.SysUser;
import com.ruoyi.common.core.domain.model.LoginUser;

/**
 * 单元测试基类：向 SecurityContextHolder 注入登录用户，
 * 供被测 Service 中的 SecurityUtils.getUsername() 静态调用使用
 *
 * @author ruoyi
 */
public abstract class BaseServiceTest {

    /** 测试登录用户名 */
    protected static final String USERNAME = "zhangsan";

    @BeforeEach
    void setUpSecurityContext() {
        SysUser sysUser = new SysUser();
        sysUser.setUserId(2L);
        sysUser.setUserName(USERNAME);
        LoginUser loginUser = new LoginUser(sysUser, new HashSet<String>());
        UsernamePasswordAuthenticationToken authentication =
                new UsernamePasswordAuthenticationToken(loginUser, null);
        SecurityContextHolder.getContext().setAuthentication(authentication);
    }

    @AfterEach
    void clearSecurityContext() {
        SecurityContextHolder.clearContext();
    }
}
