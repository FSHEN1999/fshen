# -*- coding: utf-8 -*-
"""
页面元素定位器 - Page Object Model 组织，按页面分类管理元素定位
"""

from selenium.webdriver.common.by import By


class RegistrationPage:
    """注册页面元素定位"""
    PHONE_INPUT = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[4]/div/div/div/div[2]/input")
    VERIFICATION_CODE_INPUTS = (By.XPATH, "//input[contains(@class, 'el-input__inner') and @maxlength='1']")
    NEXT_BTN = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[8]/button")


class PasswordSetupPage:
    """密码设置页面元素定位"""
    PASSWORD_INPUT = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[1]/div[2]/div/div[1]/div/input")
    CONFIRM_PASSWORD_INPUT = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[1]/div[5]/div/div[1]/div/input")
    SECURITY_QUESTION_DROPDOWN = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[2]/div[2]/div/div/div[1]/div[1]/div[2]")
    SECURITY_ANSWER_INPUT = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[2]/div[4]/div/div[1]/div/input")
    EMAIL_ADDRESS_INPUT = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[3]/div[2]/div/div[1]/div/input")
    AGREE_DECLARATION_CHECKBOX = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[4]/div/div/label/span[1]/span")
    AGREE_AUTHORIZATION_CHECKBOX = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[4]/div[2]/div/label/span[1]/span")
    REGISTER_BTN = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[1]/div/form/div[5]/div[2]/button")
    SECURITY_OPTION = (By.XPATH, "//li[contains(@class, 'el-select-dropdown__item')][1]")


class CompanyInfoPage:
    """公司信息页面元素定位"""
    COMPANY_EN_NAME_INPUT = (By.XPATH, "(//input[contains(@class, 'el-input__inner') and @autocomplete='off'])[1]")
    BUSINESS_REG_NO_INPUT = (By.XPATH, "(//input[contains(@class, 'el-input__inner') and @autocomplete='off'])[3]")
    COMPANY_CN_NAME_INPUT = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/form/div[5]/div[2]/div/div/div/input")
    BUSINESS_NATURE_SELECT = (By.XPATH, "//span[text()='企业经营性质']/ancestor::div[contains(@class, 'el-form-item')]//div[contains(@class, 'el-select')]")
    BUSINESS_NATURE_OPTIONS = (By.XPATH, "//li[contains(@class, 'el-select-dropdown__item')]")
    ESTABLISHED_DATE_INPUT = (By.XPATH, "//input[@placeholder='YYYY/MM/DD']")
    REGISTERED_ADDRESS_INPUT = (By.XPATH, "//textarea[@placeholder='请输入注册地址']")
    DISTRICT_SELECT = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/form/div[9]/div[2]/div/div[1]/div[1]/div[1]/div[2]")
    DISTRICT_FIRST_OPTION = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/form/div[9]/div[2]/div/div[1]/div[2]/div/div/div[1]/ul/li[1]")
    DETAIL_ADDRESS_INPUT = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/form/div[9]/div[3]/div/div[1]/div/input")
    SAME_ADDRESS_CHECKBOX = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/form/div[10]/div/div/div[1]/label[1]/span[1]/span")
    NO_HSBC_RELATIONSHIP_CHECKBOX = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/form/div[12]/div/div/div/label[2]/span[1]/span")
    COMPANY_REG_CERT_UPLOAD = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/form/div[2]/div[1]/div[2]/div[1]/div/div")
    BUSINESS_REG_CERT_UPLOAD = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/form/div[2]/div[2]/div[2]/div[1]/div/div")
    COMPANY_ARTICLES_UPLOAD = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/form/div[3]/div[1]/div[2]/div[1]/div/div")
    ANNUAL_RETURN_UPLOAD = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/form/div[3]/div[2]/div[2]/div[1]/div/div")
    NEXT_BTN = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div/div[2]/div/div[3]/div[2]/button[2]")


class DirectorInfoPage:
    """董事股东信息页面元素定位"""
    TITLE_DROPDOWN = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/form/div[1]/div[1]/div[2]/div/div[1]/div/div/div/div[1]/div[1]/div[2]")
    TITLE_FIRST_OPTION = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/form/div[1]/div[1]/div[2]/div/div[1]/div/div/div[1]/div[2]/div/div/div[1]/ul/li[1]")
    ID_FRONT_UPLOAD = (By.XPATH, "//div[contains(@class, 'el-upload-dragger') and .//img[contains(@src, 'PRC%20ID-Front')]]")
    ID_BACK_UPLOAD = (By.XPATH, "//div[contains(@class, 'el-upload-dragger') and .//img[contains(@src, 'PRC%20ID-Back')]]")
    BIRTH_DATE_INPUT = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/form/div[1]/div[1]/div[2]/div/div[4]/div[1]/div/div[1]/div/input")
    ID_NUMBER_INPUT = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/form/div[1]/div[1]/div[2]/div/div[4]/div[2]/div/div/div/input")
    DETAIL_ADDRESS_INPUT = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/form/div[1]/div[1]/div[2]/div/div[7]/div[2]/div/div[1]/div/input")
    GUARANTOR_CHECKBOX = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/form/div[4]/div/div[1]/div/label/span[1]/span")
    REFERENCE_PHONE = (By.XPATH, "//input[contains(@class, 'el-input__inner') and @maxlength='15']")
    REFERENCE_EMAIL = (By.XPATH, "//input[contains(@class, 'el-input__inner') and @autocomplete='off' and not(@maxlength) and not(@placeholder)]")
    NEXT_BTN = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div[5]/div[2]/button[2]")


class BankAccountPage:
    """银行账户信息页面元素定位"""
    BANK_SELECT_CONTAINER = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div/form/div[2]/div/div/div/div[1]")
    BANK_SELECT_DROPDOWN = (By.XPATH, "//input[contains(@class, 'el-select__input') and @role='combobox']")
    BANK_SELECT_OPTIONS = (By.XPATH, "//li[contains(@class, 'el-select-dropdown__item')]")
    BANK_ACCOUNT_INPUT = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div/form/div[4]/div/div/div/input")
    BANK_SELECT_SVG = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div/form/div[2]/div/div/div/div[2]/i/svg")
    NEXT_BTN = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div/div[4]/div[2]/button[2]")


class ContactInfoPage:
    """联系人信息页面元素定位"""
    CONTACT_DROPDOWN = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/form/div[2]/div[2]/div/div/div/div[1]/div[1]/div[2]")
    CONTACT_FIRST_OPTION = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/form/div[2]/div[2]/div/div/div/div[2]/div/div/div[1]/ul/li")
    SUBMIT_BTN = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div[5]/div[2]/button[2]")


class ApprovalPage:
    """审批成功后页面元素定位"""
    ACTIVATE_CREDIT_BTN = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div[1]/div[3]/div[2]/div[7]/div[2]/button")
    ACCEPT_BTN = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[3]/div/div/div/div/div/div/div[2]/div[3]/button")


class LandingPage:
    """起始页面元素定位"""
    PRODUCT_APPLY_BTN = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div/div[3]/div[1]/div[3]/button")
    INITIAL_APPLY_BTN = (By.XPATH, "//button[contains(., '立即申请')]")
    FINAL_APPLY_BTN = (By.XPATH, "/html/body/div[1]/div[1]/div[3]/div[1]/div[2]/div[1]/div[3]/div[5]/button")


# API定位器
class APILocators:
    """API相关的通用定位"""
    NEXT_BTN = (By.XPATH, "//button[contains(., '下一页')]")
