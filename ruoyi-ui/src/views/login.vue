<template>
  <div class="login">
    <el-form
      ref="loginForm"
      :model="loginForm"
      :rules="loginRules"
      label-position="top"
      hide-required-asterisk
      class="login-form"
      aria-labelledby="login-title"
      @submit.native.prevent="handleLogin"
    >
      <header class="login-header">
        <h1 id="login-title">{{ title }}</h1>
      </header>
      <el-form-item label="账号" prop="username" for="login-username">
        <el-input
          id="login-username"
          v-model="loginForm.username"
          type="text"
          autocomplete="username"
          placeholder="请输入账号"
        >
          <svg-icon slot="prefix" icon-class="user" class="input-icon" />
        </el-input>
      </el-form-item>
      <el-form-item label="密码" prop="password" for="login-password">
        <el-input
          id="login-password"
          v-model="loginForm.password"
          :type="passwordVisible ? 'text' : 'password'"
          autocomplete="current-password"
          placeholder="请输入密码"
        >
          <svg-icon slot="prefix" icon-class="password" class="input-icon" />
          <button
            slot="suffix"
            type="button"
            class="password-toggle"
            :aria-label="passwordVisible ? '隐藏密码' : '显示密码'"
            :aria-pressed="passwordVisible"
            @click="passwordVisible = !passwordVisible"
          >
            <svg-icon :icon-class="passwordVisible ? 'eye-open' : 'eye'" />
          </button>
        </el-input>
      </el-form-item>
      <el-form-item v-if="captchaEnabled" label="验证码" prop="code" for="login-code">
        <div class="captcha-row">
          <el-input
            id="login-code"
            v-model="loginForm.code"
            autocomplete="off"
            placeholder="请输入验证码"
            aria-describedby="captcha-hint"
          >
            <svg-icon slot="prefix" icon-class="validCode" class="input-icon" />
          </el-input>
          <button type="button" class="captcha-refresh" aria-label="换一张验证码" @click="getCode">
            <img :src="codeUrl" alt="验证码" />
          </button>
        </div>
      </el-form-item>
      <div class="login-options">
        <el-checkbox v-model="loginForm.rememberMe">记住密码</el-checkbox>
        <span v-if="captchaEnabled" id="captcha-hint">点击图片换一张</span>
      </div>
      <el-button :loading="loading" type="primary" native-type="submit" class="login-submit">
        <span>{{ loading ? '正在登录…' : '登录' }}</span>
        <i v-if="!loading" class="el-icon-right" aria-hidden="true" />
      </el-button>
      <div v-if="register" class="login-register">
        <router-link class="link-type" to="/register">立即注册</router-link>
      </div>
    </el-form>
  </div>
</template>

<script>
import { getCodeImg } from "@/api/login"
import Cookies from "js-cookie"
import { encrypt, decrypt } from '@/utils/jsencrypt'

export default {
  name: "Login",
  data() {
    return {
      title: process.env.VUE_APP_TITLE,
      passwordVisible: false,
      codeUrl: "",
      loginForm: {
        username: "",
        password: "",
        rememberMe: false,
        code: "",
        uuid: ""
      },
      loginRules: {
        username: [
          { required: true, trigger: "blur", message: "请输入您的账号" }
        ],
        password: [
          { required: true, trigger: "blur", message: "请输入您的密码" }
        ],
        code: [{ required: true, trigger: "change", message: "请输入验证码" }]
      },
      loading: false,
      // 验证码开关
      captchaEnabled: true,
      // 注册开关
      register: false,
      redirect: undefined
    }
  },
  watch: {
    $route: {
      handler: function(route) {
        this.redirect = route.query && route.query.redirect
      },
      immediate: true
    }
  },
  created() {
    this.getCode()
    this.getCookie()
  },
  methods: {
    getCode() {
      getCodeImg().then(res => {
        this.captchaEnabled = res.captchaEnabled === undefined ? true : res.captchaEnabled
        if (this.captchaEnabled) {
          this.codeUrl = "data:image/gif;base64," + res.img
          this.loginForm.uuid = res.uuid
        }
      })
    },
    getCookie() {
      const username = Cookies.get("username")
      const password = Cookies.get("password")
      const rememberMe = Cookies.get('rememberMe')
      this.loginForm = {
        username: username === undefined ? this.loginForm.username : username,
        password: password === undefined ? this.loginForm.password : decrypt(password),
        rememberMe: rememberMe === undefined ? false : Boolean(rememberMe)
      }
    },
    handleLogin() {
      if (this.loading) return
      this.$refs.loginForm.validate(valid => {
        if (valid) {
          this.loading = true
          if (this.loginForm.rememberMe) {
            Cookies.set("username", this.loginForm.username, { expires: 30 })
            Cookies.set("password", encrypt(this.loginForm.password), { expires: 30 })
            Cookies.set('rememberMe', this.loginForm.rememberMe, { expires: 30 })
          } else {
            Cookies.remove("username")
            Cookies.remove("password")
            Cookies.remove('rememberMe')
          }
          this.$store.dispatch("Login", this.loginForm).then(() => {
            this.$router.push({ path: this.redirect || "/" }).catch(()=>{})
          }).catch(() => {
            this.loading = false
            if (this.captchaEnabled) {
              this.getCode()
            }
          })
        }
      })
    }
  }
}
</script>

<style lang="scss" scoped>
.login {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100%;
  padding: 32px 20px;
  background: #b8cbd8 url("../assets/images/tagpilot-login-background.jpg") center / cover no-repeat;
  color: #24434a;
}
.login-form {
  width: 432px;
  max-width: 100%;
  padding: 36px;
  border-radius: 16px;
  background: #f9fbfc;
  box-shadow: 0 20px 56px rgba(32, 64, 78, 0.16);

  ::v-deep .el-form-item {
    margin-bottom: 22px;
  }
  ::v-deep .el-form-item__label {
    padding: 0 0 8px;
    color: #344f56;
    font-size: 13px;
    font-weight: 500;
    line-height: 20px;
  }
  ::v-deep .el-input__inner {
    height: 48px;
    padding-left: 40px;
    padding-right: 44px;
    border-color: #c8d6db;
    border-radius: 8px;
    background: #f2f6f7;
    color: #24434a;
    font-size: 14px;
    caret-color: #23545b;
    transition: border-color 160ms ease, background-color 160ms ease;

    &::placeholder {
      color: #647b83;
    }
    &:hover {
      border-color: #9eb6bf;
    }
    &:focus {
      border-color: #23545b;
      background: #fff;
      outline: 2px solid rgba(35, 84, 91, 0.18);
      outline-offset: 2px;
    }
    &::selection {
      background: #c8e2e3;
      color: #24434a;
    }
  }
  ::v-deep .el-input__prefix {
    left: 14px;
    display: flex;
    align-items: center;
    color: #647b83;
  }
  ::v-deep .el-input__suffix {
    right: 4px;
    display: flex;
    align-items: center;
  }
  ::v-deep .el-form-item.is-error .el-input__inner {
    border-color: #ba4242;
  }
  ::v-deep .el-form-item__error {
    color: #ba4242;
    padding-top: 5px;
  }
  ::v-deep .el-checkbox__label {
    color: #49636b;
    font-size: 13px;
  }
  ::v-deep .el-checkbox__inner {
    border-color: #9fb4bd;
    border-radius: 3px;
  }
  ::v-deep .el-checkbox__input.is-checked .el-checkbox__inner {
    border-color: #23545b;
    background-color: #23545b;
  }
  ::v-deep .el-checkbox__input.is-focus .el-checkbox__inner {
    outline: 2px solid #23545b;
    outline-offset: 3px;
  }
}
.login-header {
  margin-bottom: 32px;
  padding: 6px 0 8px;
  text-align: center;

  h1 {
    margin: 0;
    color: #24434a;
    font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: 26px;
    font-weight: 600;
    letter-spacing: 0.08em;
    line-height: 36px;
  }
}
.input-icon {
  width: 15px;
  height: 15px;
}
.password-toggle {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 40px;
  height: 40px;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #5a727c;
  cursor: pointer;

  &:hover {
    background: #e1ebee;
    color: #23545b;
  }
}
.captcha-row {
  display: flex;
  gap: 12px;

  .el-input {
    flex: 1;
    min-width: 0;
  }
  ::v-deep .el-input__inner {
    padding-right: 12px;
  }
}
.captcha-refresh {
  display: flex;
  justify-content: center;
  align-items: center;
  flex: 0 0 112px;
  height: 48px;
  padding: 4px;
  overflow: hidden;
  border: 1px solid #c8d6db;
  border-radius: 8px;
  background: #eef3f4;
  cursor: pointer;

  img {
    display: block;
    max-width: 100%;
    max-height: 100%;
  }
  &:hover {
    border-color: #23545b;
  }
}
.password-toggle:focus-visible,
.captcha-refresh:focus-visible {
  outline: 2px solid #23545b;
  outline-offset: 3px;
}
.login-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 4px 0 24px;

  span {
    color: #5a727c;
    font-size: 12px;
    line-height: 20px;
  }
}
.login-submit.el-button {
  width: 100%;
  height: 48px;
  padding: 0 20px;
  border-color: #23545b;
  border-radius: 8px;
  background: #23545b;
  color: #fff;
  font-size: 15px;
  font-weight: 500;
  transition: background-color 160ms ease;

  .el-icon-right {
    margin-left: 10px;
  }
  &:hover,
  &:focus {
    border-color: #1b444a;
    background: #1b444a;
  }
  &:focus-visible {
    outline: 2px solid #23545b;
    outline-offset: 3px;
  }
  &.is-loading {
    background: #23545b;
  }
}
.login-register {
  margin-top: 16px;
  text-align: center;
}
@media (max-width: 480px) {
  .login {
    padding: 24px 16px;
  }
  .login-form {
    padding: 28px 24px;
  }
  .captcha-refresh {
    flex-basis: 100px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .login-form ::v-deep .el-input__inner,
  .login-submit.el-button {
    transition: none;
  }
}
</style>
