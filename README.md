[toc]



# API：整合修订（1.4.5）

- 统一了命名规范，并划分了对应板块；
- 注册时，增加了校区、专业等选填项；
- 登陆成功时返回user_name,user_id,email；
- 增加了获取黑名单列表的api；
- 将私信与通知板块分开了；
- 出于规范考虑，将所有单id参数都加上了前缀；
- 添加了获取某用户对某课程评价的api；
- 创建完Article/Post/Reply之后会返回对应id，方便跳转；
- 给Post类也加一个收藏功能，毕竟提问的帖子也需要收藏一下
- 1.4.1修订：修正了**获取某个用户对某个课程的评价**中请求参数的错误；为**创建课程**新增了campus字段表示校区，college的备注更改为学院
- 1.4.2修订：添加**根据课程id分页获取对课程评价评分列表**的api；创建文章时添加**资源链接**，**封面链接**，**文章描述**的字段
- 1.4.3修订：移除了Post的tags，感觉没用
- 1.4.3修订：课程评价与评分单开一个了`CourseReview`类，后续重构时考虑使其继承post类，或者单开一个关联reply；
- 1.4.3修订：点赞板块的content_type改成int类型了，考虑到比较高频，还是int性能好一点
- 1.4.3修订：点赞操作的`user_id`参数没必要，可以直接从header的`access token`获取
- 1.4.3修订：简单把身份认证部分的返回形式改成了`status`+`message`，原生报错考虑一下要不要改，目前来说感觉没啥必要
- 1.4.4修订：增加了用户主页的api，简单进行了缓存优化；
- 1.4.4修订：增加了获取文章图片的api，这一块重构了不少；
- 1.4.4修订：写了权限设置和屏蔽管理，不过是初步的，后续感觉还要优化；
- 1.4.5修订：修改了reply创建的视图函数，使其可以回复reply
- 1.4.5修订：**通知和私信部分做了较大改动**，发送通知改成钩子函数直接在后端调用，移除了部分无用的`user_id`；`notification_list`增加了更多返回值。
- 1.4.5修订：获取用户头像的api传参改为`user_id`
- 1.4.5修订：**base_url由`/index`改为`/index/api`，方便后续维护**
- 1.4.5修订：**收藏部分进行了重构**，包括api的重命名和结构整合，删去了无意义的user_id，修复部分bug
- 1.4.5修订：增加了获取用户列表的api

Todo：

- 写一下搜索功能
- 文档里的类之后可能会修改，仅供参考
- 状态码待完善
- 封禁系统需要简单完善一下
- sdu邮箱换绑需要支持
- 一些缓存/索引优化
- 置顶功能的api
- 目前基础部分就差封禁/管理员的部分，工作量不大，尽量本周写完
- course需要保存每一个修改版本，且修改需要经过管理员审核，标记贡献者等；每个课程可以由管理员进行冻结，冻结后不接受任何提交。
- 贡献值/荣誉分等细节，应该搞一个按照影响力排序的用户列表，为用户添加总获赞数之类的
- 有空的时候可以做一下关注操作
- 屏蔽词/图片违规检测



## 0.自定义JWT认证

简单说下，后续会补充详细版本+状态码说明。

用户登录后可以获取Access_Token和Refresh_Token，其中Access_Token每小时过期一次，Refresh_Token每星期过期一次。

需要在header添加如下内容：

```
Authorization: Bearer <access_token>
```

示例：

```
Authorization: Bearer 
eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjo...
```

Access_Token过期后需要通过`GET index/api/refresh`（请求参数为`"refresh":<refresh_token>`）来获取新token。



## 1.账户板块（登录，登出，注册，注销）

### （0）用户的类

```python
# 继承AbstractUser, 自带id, username，password，created_at

class User(AbstractUser):
	email = models.EmailField(unique=True)  # 确保email唯一
    email_code = models.IntegerField(null=True, blank=True) # 验证码
    reputation = models.IntegerField(default=100) # 信誉分
    all_likes = models.IntegerField(default=0) # 获得的总点赞数
    all_views = models.IntegerField(default=0) # 获得的总浏览量
    all_articles = models.IntegerField(default=0) # 发布的总文章数
    all_posts = models.IntegerField(default=0) # 发布的总帖子数
    all_replys = models.IntegerField(default=0) # 发布的总回复数
    influence = models.IntegerField(default=0) # 影响力因子
    master = models.BooleanField(default=False) # 是否是管理员
    super_master = models.BooleanField(default=False) # 是否是超级管理员
    block = models.BooleanField(default=False) # 是否处于封禁状态
    block_end_time = models.DateTimeField(null=True, blank=True) # 封禁结束时间
    blocklist = models.ManyToManyField('self', symmetrical=False, related_name='blocked_by', through='BlockList') #与blocklist关联
    profile_url = models.CharField(max_length=255, null=True, blank=True) # 头像url
    campus = models.CharField(max_length=255, null=True, blank=True) # 校区
    college = models.CharField(max_length=255, null=True, blank=True) # 学院
    major = models.CharField(max_length=255, null=True, blank=True) # 专业

    def __str__(self):
        return self.username
```

---

### （1）注册

#### **url : `/index/register`**

**<1> POST `/register`**

**描述：**  
此接口用于注册，包括用户名、密码、电子邮件、邮箱验证码及其他用户信息（如校区、学院、专业，选填）的提交。

**请求参数：**

| 参数名       | 类型   | 必填 | 描述                                                        |
| ------------ | ------ | ---- | ----------------------------------------------------------- |
| `user_name`  | string | 是   | 用户名，需唯一。                                            |
| `pass_word`  | string | 是   | 用户密码。                                                  |
| `email`      | string | 是   | 用户邮箱，需唯一。                                          |
| `email_code` | string | 是   | 邮箱验证码，通过 `/register?send_code=1&email=email` 获取。 |
| `campus`     | string | 否   | 校区信息，例如：青岛，兴隆山，千佛山等。                    |
| `college`    | string | 否   | 学院信息，例如：计算机科学与技术学院、数学学院等。          |
| `major`      | string | 否   | 专业信息，例如：计算机科学与技术、软件工程等。              |

**响应参数（注：之后的响应参数，如无特殊说明均使用status+message的形式）：**

| 参数名    | 类型   | 描述       |
| --------- | ------ | ---------- |
| `status`  | int    | 状态码。   |
| `message` | string | 返回信息。 |

- **200 OK**: 注册成功；
- **400 Bad Request**: 注册请求的参数错误或缺失；
- **409 Conflict**: 注册冲突，例如用户名或邮箱已存在；
- **429 Too Many Requests**: 注册请求过多，例如短时间内多次尝试注册；
- **430 Invalid Email**: 邮箱格式有误，非山大邮箱；
- **431 Block Email**: 邮箱注销冷却中；
- **500 Internal Server Error**: 服务器内部错误；

**<2> GET `/register?send_code=1&email=email`**

**描述：**  
此接口用于向指定的邮箱发送验证码，用于验证用户邮箱。

**请求参数：**

| 参数名  | 类型   | 必填 | 描述           |
| ------- | ------ | ---- | -------------- |
| `email` | string | 是   | 目标邮箱地址。 |

**响应参数：**

| 参数名    | 类型   | 描述       |
| --------- | ------ | ---------- |
| `status`  | int    | 状态码。   |
| `message` | string | 返回信息。 |

- **200 OK**: 验证码获取成功；
- **404 Not Found**: 验证码未找到或已过期；
- **429 Too Many Requests**: 验证码请求过多，例如短时间内多次请求验证码；
- **500 Internal Server Error**: 服务器内部错误；

---

### （2）用户名和密码登录

#### **url：`/index/login_passwd`**

**POST `/login_passwd`**

**描述：**  
用户登录接口。此接口用于登录，提交用户的用户名和密码。

**请求参数：**

| 参数名      | 类型   | 必填 | 描述             |
| ----------- | ------ | ---- | ---------------- |
| `user_name` | string | 是   | 用户名，需唯一。 |
| `pass_word` | string | 是   | 用户密码。       |

**响应参数：**

| 参数名      | 类型   | 描述       |
| ----------- | ------ | ---------- |
| `status`    | int    | 状态码。   |
| `message`   | string | 返回信息。 |
| `user_id`   | string | 用户id。   |
| `user_name` | string | 用户名。   |
| `email`     | string | 用户邮箱。 |

- **200 OK**: 登录成功，返回用户基本信息；
- **401 Unauthorized**: 用户名或密码错误；
- **423 Locked**: 账号被锁定，例如因多次登录失败；
- **429 Too Many Requests**: 登录请求过多，例如短时间内多次尝试登录；

---

### （3）邮箱和验证码登录

#### **url：`/index/login_email`**

**<1> POST `/login_email`**

**描述：**  
此接口用于登录，提交用户的邮箱和验证码。

**请求参数：**

| 参数名       | 类型   | 必填 | 描述                                                         |
| ------------ | ------ | ---- | ------------------------------------------------------------ |
| `email`      | string | 是   | 用户邮箱，需唯一。                                           |
| `email_code` | string | 是   | 邮箱验证码，通过 `/login_email?send_code=1&email=email` 获取。 |

**响应参数：**

| 参数名      | 类型   | 描述       |
| ----------- | ------ | ---------- |
| `status`    | int    | 状态码。   |
| `message`   | string | 返回信息。 |
| `user_id`   | string | 用户id。   |
| `user_name` | string | 用户名。   |
| `email`     | string | 用户邮箱。 |

- **200 OK**: 登录成功，返回用户基本信息；
- **401 Unauthorized**: 邮箱或验证码错误；
- **423 Locked**: 账号被锁定，例如因多次登录失败；
- **429 Too Many Requests**: 登录请求过多，例如短时间内多次尝试登录；

**<2> GET `/login_email?send_code=1&email=email`**

**描述：**  
此接口用于向指定的邮箱发送验证码，用于验证用户邮箱。

**请求参数：**

| 参数名  | 类型   | 必填 | 描述           |
| ------- | ------ | ---- | -------------- |
| `email` | string | 是   | 目标邮箱地址。 |

**响应参数：**

| 参数名    | 类型   | 描述       |
| --------- | ------ | ---------- |
| `status`  | int    | 状态码。   |
| `message` | string | 返回信息。 |

- **200 OK**: 验证码获取成功；
- **404 Not Found**: 验证码未找到或已过期；
- **429 Too Many Requests**: 验证码请求过多，例如短时间内多次请求验证码；
- **500 Internal Server Error**: 服务器内部错误；

---


### （4）登出

#### **url：`/index/logout`**

**POST `/logout`**

**描述：** 
此接口用于退出登录。退出登录后自动关闭会话，无需请求参数。

**响应参数：**

- **200 OK**: 登出成功；
- **500 Internal Server Error**: 服务器内部错误；


### （5）注销账户

#### **url：`/index/delete_account`**

**<1> POST `/delete_account`**

**描述：** 
此接口用于注销账户，提交用户的用户名和邮箱。

**请求参数：**

| 参数名       | 类型   | 必填 | 描述                                                         |
| ------------ | ------ | ---- | ------------------------------------------------------------ |
| `user_name`  | string | 是   | 用户名，需唯一。                                             |
| `email`      | string | 是   | 目标邮箱地址。                                               |
| `email_code` | string | 是   | 邮箱验证码，通过`/delete_account?send_code=1&email=email`获取 |

**响应参数：**

- **200 OK**: 注销成功。

- **404 Not Found**: 邮箱或验证码错误。

- **401 Unauthorized**: 用户不存在。

**<2> GET `/delete_account?send_code=1&email=email`**

**描述：**
此接口用于向指定的邮箱发送验证码，用于验证用户邮箱。

**请求参数：**

| 参数名  | 类型   | 必填 | 描述           |
| ------- | ------ | ---- | -------------- |
| `email` | string | 是   | 目标邮箱地址。 |

**响应参数：**

- **200 OK**: 验证码获取成功；

- **404 Not Found**: 验证码未找到或已过期。

- **429 Too Many Requests**:  验证码请求过多，例如短时间内多次请求验证码；

- **500 Internal Server Error**: 服务器内部错误；

### （5）重置密码

#### **url：`/index/reset_password`**

**<1>POST `/reset_password`**

**描述：** 
此接口用于重置密码，提交用户的用户名和邮箱。

**请求参数：**

| 参数名          | 类型   | 必填 | 描述                                                         |
| --------------- | ------ | ---- | ------------------------------------------------------------ |
| `email`         | string | 是   | 目标邮箱地址。                                               |
| `new_pass_word` | string | 是   | 新密码。                                                     |
| `email_code`    | string | 是   | 重置密码的验证码，通过 `/reset_password?send_code=1&email=email` 获取。 |

**响应参数：**

- **200 OK**: 重置密码成功。

- **401 Unauthorized**: 邮箱或验证码错误。

- **423 Locked**: 短时间内频繁修改，已锁定。

 **<2>GET /reset_password?send_code=1&email=email**

 **描述：**
此接口用于向指定的邮箱发送验证码，用于验证用户邮箱。

**请求参数：**

| 参数名  | 类型   | 必填 | 描述           |
| ------- | ------ | ---- | -------------- |
| `email` | string | 是   | 目标邮箱地址。 |

**响应参数：**

- **200 OK**: 验证码获取成功；
- **404 Not Found**: 验证码未找到或已过期。
- **429 Too Many Requests**:  验证码请求过多，例如短时间内多次请求验证码；
- **500 Internal Server Error**: 服务器内部错误；

### （6）用户主页

#### **url：`/index/homepage`**

**GET `/homepage?user_id=user_id`**

**描述：**
此接口用于获取用户主页。

**请求参数：**

| 参数名    | 类型 | 必填 | 描述                                                |
| --------- | ---- | ---- | --------------------------------------------------- |
| `user_id` | int  | 否   | 目标用户的user_id，若为空则默认返回用户自己的主页。 |

**响应参数：**

| 参数名    | 类型   | 描述       |
| --------- | ------ | ---------- |
| `status`  | int    | 状态码。   |
| `message` | string | 返回信息。 |
| `data`    | list   | 用户信息   |

- **200 OK**: 获取用户主页成功；
- **404 Unauthorized**: 用户不存在；
- **500 Internal Server Error**: 服务器内部错误；


**若获取成功，且获取的为用户自己的主页，则 `data` 的内容如下：**

| 参数名             | 类型   | 描述                                                       |
| ------------------ | ------ | ---------------------------------------------------------- |
| `user_id`          | int    | 用户的ID。                                                 |
| `user_name`        | string | 用户名。                                                   |
| `email`            | string | 用户的邮箱。                                               |
| `profile_url`      | string | 用户的头像地址。                                           |
| `reputation`       | int    | 用户荣誉分。                                               |
| `reputation_level` | string | 用户荣誉等级。                                             |
| `master`           | bool   | 是否是管理员。                                             |
| `super_master`     | bool   | 是否是超级管理员。                                         |
| `campus`           | string | 用户的校区。                                               |
| `college`          | string | 用户的学院。                                               |
| `major`            | string | 用户的专业。                                               |
| `all_articles`     | int    | 用户的总文章数。                                           |
| `all_posts`        | int    | 用户的总帖子数。                                           |
| `all_replys`       | int    | 用户的总回复数。                                           |
| `created_at`       | time   | 用户注册时间，格式参考`2025-02-09T15:40:01.006600+00:00`。 |
| `block_status`     | bool   | 用户是否被封禁。                                           |
| `block_end_time`   | time   | 如果被封禁的话，封禁什么时候结束。                         |

**若获取成功，且获取的不是用户自己的主页，则 `data` 的内容如下：**

| 参数名              | 类型   | 描述               |
| ------------------- | ------ | ------------------ |
| `user_id`           | int    | 用户的ID。         |
| `user_name`         | string | 用户名。           |
| `email`             | string | 用户的邮箱。       |
| `profile_url`       | string | 用户的头像地址。   |
| `reputation_level`  | string | 用户荣誉等级。     |
| `master`            | bool   | 是否是管理员。     |
| `super_master`      | bool   | 是否是超级管理员。 |
| `campus`            | string | 用户的校区。       |
| `college`           | string | 用户的学院。       |
| `major`             | string | 用户的专业。       |
| `registration_year` | int    | 用户注册的年份。   |
| `block_status`      | bool   | 用户是否被封禁。   |


### （6）用户列表（按照荣誉分排序，master和super_master置顶）

#### **url：`/index/user/list`**

**GET `/user/list`**

**描述：**
此接口用于获取用户列表，按照荣誉分排序，`master`和`super_master`置顶。

**请求参数：**

无

**响应参数：**

| 参数名    | 类型   | 描述       |
| --------- | ------ | ---------- |
| `status`  | int    | 状态码。   |
| `message` | string | 返回信息。 |
| `user_list`    | array   | 用户对象数组   |

- **200 OK**: 获取用户列表成功；
- **404 Unauthorized**: 用户不存在；
- **500 Internal Server Error**: 服务器内部错误；


**若获取成功，则 `user_list` 的每个对象内容如下：**

| 参数名    | 类型   | 描述       |
| --------- | ------ | ---------- |
| `user_id`  | int   | 用户id。   |
| `user_name` | string | 用户名。 |
| `reputation_level`| string  | 用户荣誉等级|
| `all_likes` | int | 用户获得的点赞数 |
| `all_articles`| int  | 用户创建的总文章数|
| `master`            | bool   | 是否是管理员。     |
| `super_master`      | bool   | 是否是超级管理员。 |



## 2.黑名单板块

### （0）黑名单类

```python
class BlockList(models.Model):
    from_user = models.ForeignKey(User, related_name='blocking', on_delete=models.CASCADE)
    to_user = models.ForeignKey(User, related_name='blocked', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('from_user', 'to_user')
```

### （1）拉黑用户

#### **url：`/index/block`**

**POST `/block`**

**描述：**
此接口用于拉黑其他用户。

**请求参数：**

| 参数名       | 类型 | 必填 | 描述           |
| ------------ | ---- | ---- | -------------- |
| `to_user_id` | int  | 是   | 被拉黑者的id。 |

**响应参数：**

- **200 OK**: 拉黑用户成功。

- **409 Conflict**: 已经拉黑过该用户。

- **404 Not Found**: 用户未找到或已注销。

- **500 Internal Server Error**: 服务器内部错误；


### （2）解除拉黑

#### **url：`/index/unblock`**

**POST `/unblock`**

**描述：**
此接口用于解除对用户的拉黑。

**请求参数：**

| 参数名       | 类型 | 必填 | 描述           |
| ------------ | ---- | ---- | -------------- |
| `to_user_id` | int  | 是   | 被拉黑者的id。 |

**响应参数：**

- **200 OK**: 解除拉黑成功。
- **401 Unauthorized**：尚未拉黑该用户，无需解除。
- **404 Not Found**: 用户未找到或已注销。
- **500 Internal Server Error**: 服务器内部错误；

---

### （3）获取黑名单列表

#### **url：`/index/blocklist`**

**GET `/blocklist?user_id=user_id`**

**描述：**  
此接口用于获取当前用户的黑名单列表。返回拉黑的用户信息，包括用户名、ID、头像等。

**请求参数：**

| 参数名    | 类型 | 必填 | 描述                             |
| --------- | ---- | ---- | -------------------------------- |
| `user_id` | int  | 是   | 当前用户的ID，用于查询消息列表。 |

**响应参数：**

| 参数名       | 类型   | 描述                                   |
| ------------ | ------ | -------------------------------------- |
| `status`     | int    | 状态码。                               |
| `message`    | string | 返回信息。                             |
| `block_list` | array  | 黑名单列表，包含被拉黑用户的基本信息。 |

- **200 OK**: 获取黑名单列表成功；
- **401 Unauthorized**: 用户未登陆或无权限获取他人黑名单；
- **500 Internal Server Error**: 服务器内部错误；


**若获取成功，则 `block_list` 的每个对象内容如下：**

| 参数名         | 类型   | 描述                   |
| -------------- | ------ | ---------------------- |
| `to_user_id`   | int    | 被拉黑用户的ID。       |
| `to_user_name` | string | 被拉黑用户的用户名。   |
| `email`        | string | 被拉黑用户的邮箱。     |
| `profile_url`  | string | 被拉黑用户的头像地址。 |


---

## 3.Article板块

### （0）Article的类

```python
class Article(models.Model):
    ARTICLE_TYPE_CHOICES = [
        ('original', '原创'),
        ('repost', '转载'),
    ]

    id = models.AutoField(primary_key=True)
    article_title = models.CharField(max_length=255, verbose_name="文章标题")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='articles', verbose_name="作者")
    content = models.TextField(verbose_name="内容")
    tags = models.ManyToManyField('Tag', related_name='articles', verbose_name="标签")
    stars = models.PositiveIntegerField(default=0, verbose_name="收藏数")
    likes = GenericRelation(Like, verbose_name="点赞")
    views = models.PositiveIntegerField(default=0, verbose_name="浏览量")
    block = models.BooleanField(default=False, db_index=True, verbose_name="是否屏蔽")
    publish_time = models.DateTimeField(auto_now_add=True, verbose_name="发布时间")
    origin_link = models.CharField(max_length=255, blank=True, null=True, verbose_name="原文链接")
    resource_link = models.CharField(max_length=255, blank=True, null=True, verbose_name="资源URL")
    article_summary = models.CharField(max_length=255, blank=True, null=True, default="这个人没有写简介...", verbose_name="文章简介")
    cover_link = models.CharField(max_length=255, blank=True, null=True, default="后续改成默认封面？或者检查到空就不加载", verbose_name="封面URL")
    article_type = models.CharField(
        max_length=10,
        choices=ARTICLE_TYPE_CHOICES,
        default='original',
        verbose_name="文章类型"
    )

    def __str__(self):
        return self.article_title

    class Meta:
        verbose_name = "文章"
        verbose_name_plural = "文章"
        indexes = [
            models.Index(fields=['-publish_time']),  # 显式定义索引
        ]
        ordering = ['-publish_time']

class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True, db_index=True, verbose_name="标签名")  # 添加索引
    
    def __str__(self):
        return self.name
```

### （1）创建article

#### **url：`/index/article/create`**

**POST `/article/create`**

**请求参数：**

| 参数名            | 类型   | 必填 | 描述                   |
| ----------------- | ------ | ---- | ---------------------- |
| `article_title`   | string | 是   | 文章标题。             |
| `content`         | string | 是   | 文章内容。             |
| `tags`            | string | 否   | 文章标签。以逗号分隔。 |
| `article_type`    | string | 否   | 文章类型：原创或转载。 |
| `origin_link`     | string | 否   | 转载时的原文链接。     |
| `resource_link`   | string | 否   | 资源链接               |
| `cover_link`      | string | 否   | 封面链接               |
| `article_summary` | string | 否   | 文章简介               |

**响应参数：**

| 参数名       | 类型   | 描述                                    |
| ------------ | ------ | --------------------------------------- |
| `status`     | int    | 状态码。                                |
| `message`    | string | 返回信息。                              |
| `article_id` | int    | 若创建成功则返回article的id，方便跳转。 |

- **200 OK**: 创建文章成功。

- **500 Internal Server Error**: 服务器内部错误；


---

### （2）编辑article

#### **url：`/index/article/edit`**

**POST `/article/edit`**

**请求参数：**

| 参数名          | 类型   | 必填 | 描述                   |
| --------------- | ------ | ---- | ---------------------- |
| `article_id`    | int    | 是   | 文章的id。             |
| `article_title` | string | 否   | 文章标题。             |
| `content`       | string | 否   | 文章内容。             |
| `tags`          | string | 否   | 文章标签。以#号分隔。  |
| `article_type`  | string | 否   | 文章类型：原创或转载。 |
| `origin_link`   | string | 否   | 转载时的原文链接。     |

**响应参数：**

- **200 OK**: 编辑文章成功。

- **500 Internal Server Error**: 服务器内部错误；


---

### （3）删除article

#### **url：`/index/article/delete`**

**POST `/article/delete`**

**描述：**
此接口用于删除article。

**请求参数：**

| 参数名       | 类型 | 必填 | 描述       |
| ------------ | ---- | ---- | ---------- |
| `article_id` | int  | 是   | 文章的id。 |

**响应参数：**

- **200 OK**: 删除文章成功。

- **500 Internal Server Error**: 服务器内部错误；

---

### （4）通过id获取Article的详细信息

#### **url：`/index/article/detail`**

**GET `/article/detail?article_id=article_id`**

**请求参数：**

| 参数名       | 类型 | 必填 | 描述       |
| ------------ | ---- | ---- | ---------- |
| `article_id` | int  | 是   | 文章的id。 |

**响应参数：**

| 参数名           | 类型   | 描述       |
| ---------------- | ------ | ---------- |
| `status`         | int    | 状态码。   |
| `message`        | string | 返回信息。 |
| `article_detail` | list   | 文章详情。 |

- **200 OK**: 获取文章详情成功。

- **500 Internal Server Error**: 服务器内部错误；

若获取成功，则`article_detail`的内容如下：

| 参数名               | 类型   | 描述                             |
| -------------------- | ------ | -------------------------------- |
| `article_id`         | int    | 文章id。                         |
| `article_title`      | string | 文章题目。                       |
| `article_content`    | string | 文章内容。                       |
| `article_type`       | string | 转载/原创。                      |
| `origin_link`        | string | 若为转载，则标注原帖。           |
| `article_tags`       | array  | 文章的标签。                     |
| `author_name`        | string | 作者的名字。                     |
| `author_profile_url` | string | 作者头像的url。                  |
| `like_count`         | int    | 总点赞数。                       |
| `star_count`         | int    | 总收藏数。                       |
| `view_count`         | int    | 总浏览量。                       |
| `reply_count`        | int    | 总回复量（包括文章评论及回复）。 |
| `source_url`         | string | 资源链接。                       |
| `publish_time`       | time   | 文章发布时间。                   |
| `if_like`            | bool   | 是否已经点赞过。                 |
| `if_star`            | bool   | 是否已经收藏过。                 |

---

### （5）根据id分页获取Article下的Post列表

#### **url：`/index/article/post_list`**

**GET `/article/post_list?article_id=aticle_id&page_index=page_index&page_size=page_size`**

**描述：**
此接口用于获取指定文章（通过文章ID）下，按分页要求返回的Post列表。

**请求参数：**

| 参数名       | 类型 | 必填 | 描述                           |
| ------------ | ---- | ---- | ------------------------------ |
| `article_id` | int  | 是   | 文章ID。                       |
| `page_index` | int  | 否   | 第几页，默认为第一页。         |
| `page_size`  | int  | 否   | 每页显示的Post数量，默认为20。 |

**响应参数：**

| 参数名      | 类型   | 描述       |
| ----------- | ------ | ---------- |
| `status`    | int    | 状态码。   |
| `message`   | string | 返回信息。 |
| `post_list` | array  | Post列表。 |

- **200 OK**: 获取Post列表成功。
- **500 Internal Server Error**: 服务器内部错误。

若获取成功，则`post_list`中的每个Post对象的内容如下：

| 参数名               | 类型   | 描述             |
| -------------------- | ------ | ---------------- |
| `post_id`            | int    | 帖子ID。         |
| `post_title`         | string | 帖子标题。       |
| `post_content`       | string | 帖子内容。       |
| `poster_name`        | string | 发帖人名称。     |
| `poster_profile_url` | string | 发帖人头像URL。  |
| `view_count`         | int    | 帖子的浏览量。   |
| `like_count`         | int    | 帖子的点赞数。   |
| `reply_count`        | int    | 帖子的回复数。   |
| `tags`               | array  | 帖子的标签。     |
| `publish_time`       | time   | 帖子的发布时间。 |
| `if_like`            | bool   | 是否已经点赞过。 |

---

### （6）分页获取article列表（支持按时间/收藏/浏览量等排序，支持tag筛选）

忘记做like了筛选了，是不是合并成热度会好一点

#### **url：`/index/article/list`**

**GET `/article/list?page_index=1&page_size=20&tags=1,2&sort=time`**

**请求参数：**

| 参数名     | 类型   | 必填 | 描述/可选值                      |
| ---------- | ------ | ---- | -------------------------------- |
| page_index | int    | 否   | 页码，默认1                      |
| page_size  | int    | 否   | 每页数量，默认20                 |
| tags       | string | 否   | 逗号分隔的标签ID                 |
| sort       | string | 否   | 排序方式：time（默认）/star/view |

**响应参数：**

| 参数名       | 类型   | 描述     |
| ------------ | ------ | -------- |
| status       | int    | 状态码   |
| message      | string | 返回信息 |
| article_list | array  | 文章数据 |
| total_pages  | int    | 总页数   |
| current_page | int    | 当前页码 |

**文章对象结构：**

| 字段名             | 类型   | 描述              |
| ------------------ | ------ | ----------------- |
| article_id         | int    | 文章ID            |
| article_title      | string | 文章标题          |
| author_name        | string | 作者名称          |
| author_profile_url | string | 作者头像URL       |
| star_count         | int    | 收藏数            |
| view_count         | int    | 浏览量            |
| like_count         | int    | 点赞数            |
| tags               | array  | 标签名称列表      |
| publish_time       | string | 发布时间          |
| article_summary    | string | 文章简介          |
| cover_link         | string | 封面URL           |
| article_type       | string | 类型（原创/转载） |


---


## 4.Post与Reply板块

### （0）Post与Reply类

**Post类如下：**

```python
class Post(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="帖子ID")
    post_title = models.CharField(
        max_length=255,
        verbose_name="帖子标题",
        help_text="标题最多255个字符",
        db_index=True  # 添加标题索引
    )
    poster = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='posts',
        verbose_name="发帖人",
        db_index=True  # 外键索引
    )
    content = models.TextField(
        verbose_name="内容",
        help_text="支持Markdown格式"
    )
    views = models.PositiveIntegerField(
        default=0,
        verbose_name="浏览量",
        help_text="通过原子操作更新"
    )
    likes = GenericRelation(
        'Like',
        verbose_name="点赞",
        related_query_name='post'  # 优化反向查询
    )
    block = models.BooleanField(
        default=False,
        verbose_name="是否屏蔽",
        db_index=True  # 高频过滤字段索引
    )
    top = models.BooleanField(
        default=False,
        verbose_name="是否置顶",
        db_index=True  # 高频排序字段索引
    )
    publish_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name="发布时间",
        db_index=True  # 时间索引
    )
    article = models.ForeignKey(
        'Article',
        on_delete=models.SET_NULL,  # 文章删除后保留帖子
        related_name='posts',
        null=True,
        blank=True,
        verbose_name="关联文章",
        db_index=True
    )
    course = models.ForeignKey(
        'Course',
        on_delete=models.SET_NULL,  # 课程删除后保留帖子
        related_name='posts',
        null=True,
        blank=True,
        verbose_name="关联课程",
        db_index=True
    )
    hot_score = models.FloatField(
        default=0.0,
        verbose_name="热度分",
        db_index=True,
        help_text="计算公式：浏览量×0.3 + 点赞数×0.7",
        editable=False  # 防止人工修改
    )

    class Meta:
        verbose_name = "帖子"
        verbose_name_plural = "帖子"
        ordering = ['-publish_time']  # 默认时间倒序
        indexes = [
            # 置顶+时间联合索引
            models.Index(fields=['top', '-publish_time']),
            # 作者+时间联合索引
            models.Index(fields=['poster', '-publish_time']),
            models.Index(fields=['article', '-publish_time']),
            models.Index(fields=['course', '-publish_time']),
            # 优化排序查询
            models.Index(fields=['-views']),
            models.Index(fields=['-hot_score']),
            models.Index(fields=['-publish_time', 'block']),
            # 热度分排序索引
            models.Index(fields=['-hot_score', '-publish_time']),
            # 联合查询优化
            models.Index(fields=['block', '-hot_score']),
        ]
        get_latest_by = 'publish_time'

    def __str__(self):
        return f"{self.post_title[:20]}（{self.poster.username}@{self.publish_time:%Y-%m-%d}）"

    def save(self, *args, **kwargs):
        """保存前校验必填字段"""
        if not self.post_title.strip():
            raise ValueError("帖子标题不能为空")
        if len(self.content.strip()) < 10:
            raise ValueError("内容至少需要10个有效字符")
        super().save(*args, **kwargs)

    @property
    def reply_count(self):
        """实时统计回复数（可缓存优化）"""
        return self.replies.count()
    
    def update_hot_scores():
        Post.objects.update(
            hot_score=0.3 * F('views') + 0.7 * F('like_count')
        )

    def increment_views(self):
        """原子操作更新浏览量"""
        Post.objects.filter(id=self.id).update(views=models.F('views') + 1)
```

**Reply类如下：**

```python
class Reply(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="回复ID")
    reply_content = models.TextField(verbose_name="回复内容", help_text="回复内容最多支持5000字符")
    reply_time = models.DateTimeField(auto_now_add=True, verbose_name="回复时间", db_index=True)
    
    post = models.ForeignKey(
        'Post',
        on_delete=models.CASCADE,
        related_name='replies',
        verbose_name="关联帖子",
        db_index=True
    )
    
    replier = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='replies',
        verbose_name="回复用户",
        db_index=True
    )
    
    parent_reply = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="父级回复",
        db_index=True
    )
    
    likes = GenericRelation(
        'Like',
        verbose_name="点赞",
        help_text="通过GenericForeignKey实现的通用点赞关系"
    )

    class Meta:
        verbose_name = "帖子回复"
        verbose_name_plural = "帖子回复"
        ordering = ['-reply_time']
        indexes = [
            models.Index(fields=['post', 'parent_reply', '-reply_time']),
            models.Index(fields=['replier', '-reply_time']),
        ]

    def __str__(self):
        return f"{self.replier.username} → {self.post.post_title[:20]}（{self.reply_time:%Y-%m-%d}）"

    def save(self, *args, **kwargs):
        if len(self.reply_content.strip()) < 5:
            raise ValueError("回复内容至少需要5个有效字符")
        super().save(*args, **kwargs)

    def save(self, *args, **kwargs):
        """保存前自动校验内容长度"""
        if len(self.reply_content.strip()) < 5:
            raise ValueError("回复内容至少需要5个有效字符")
        super().save(*args, **kwargs)
```

### （1）在Article下发帖

#### **url：`/index/post/article_post`**

**POST `/post/article_post`**

**描述：**
此接口用于在文章下创建post。

**请求参数：**

| 参数名         | 类型   | 必填 | 描述       |
| -------------- | ------ | ---- | ---------- |
| `article_id`   | int    | 是   | 文章id。   |
| `post_title`   | string | 否   | 帖子标题。 |
| `post_content` | string | 是   | 帖子内容。 |

**响应参数：**

| 参数名    | 类型   | 描述                                 |
| --------- | ------ | ------------------------------------ |
| `status`  | int    | 状态码。                             |
| `message` | string | 返回信息。                           |
| `post_id` | int    | 若创建成功则返回post的id，方便跳转。 |

- **201 Created**: 帖子创建成功。
- **400 Bad Request**: 请求参数不完整或格式错误。

---

### （2）在Course下发帖

此处发帖实际上表示的是提问，不涉及评分，故不支持修改

#### **url：`/index/post/course_post`**

**POST `/post/course_post`**

**描述：**
此接口用于在课程下创建post。

**请求参数：**

| 参数名         | 类型   | 必填 | 描述       |
| -------------- | ------ | ---- | ---------- |
| `post_title`   | string | 否   | 帖子标题。 |
| `post_content` | string | 是   | 帖子内容。 |

**响应参数：**

| 参数名    | 类型   | 描述                                 |
| --------- | ------ | ------------------------------------ |
| `status`  | int    | 状态码。                             |
| `message` | string | 返回信息。                           |
| `post_id` | int    | 若创建成功则返回post的id，方便跳转。 |

- **201 Created**: 帖子创建成功。
- **400 Bad Request**: 请求参数不完整或格式错误。

---

### （3）通过id获取Post的详细信息

#### **url：`/index/post/detail`**

**GET `/post/detail?post_id=post_id`**

**描述：**
此接口用于获取指定Post的详细信息。

**请求参数：**

| 参数名    | 类型 | 必填 | 描述       |
| --------- | ---- | ---- | ---------- |
| `post_id` | int  | 是   | 帖子的id。 |

**响应参数：**

| 参数名        | 类型   | 描述       |
| ------------- | ------ | ---------- |
| `status`      | int    | 状态码。   |
| `message`     | string | 返回信息。 |
| `post_detail` | array  | 帖子详情。 |

- **200 OK**: 获取Post详情成功，返回详细信息。
- **404 Not Found**: 未找到指定的帖子。
- **400 Bad Request**: 请求参数不合法。

若获取成功，则`post_detail`的参数如下：

| 参数名               | 类型   | 描述              |
| -------------------- | ------ | ----------------- |
| `post_id`            | int    | 帖子id。          |
| `post_title`         | string | 帖子标题。        |
| `post_content`       | string | 帖子内容。        |
| `poster_name`        | string | 发帖人的名字。    |
| `poster_profile_url` | string | 发帖人头像的url。 |
| `view_count`         | int    | 帖子的浏览量。    |
| `like_count`         | int    | 帖子的点赞数。    |
| `reply_count`        | int    | 帖子的回复数。    |
| `publish_time`       | time   | 帖子的发布时间。  |

---

### （4）根据id分页获取Post下的Reply列表

#### **url：`/index/post/reply_list`**

**GET `/post/reply_list?post_id=post_id&page_index=page_index&page_size=page_size`**

**描述：**
此接口用于根据Post的id分页获取Reply列表。

**请求参数：**

| 参数名       | 类型 | 必填 | 描述                           |
| ------------ | ---- | ---- | ------------------------------ |
| `post_id`    | int  | 是   | post对应id。                   |
| `page_index` | int  | 否   | 第几页，默认为第一页。         |
| `page_size`  | int  | 否   | 每页显示的回复数量，默认为20。 |

**响应参数：**

| 参数名       | 类型   | 描述       |
| ------------ | ------ | ---------- |
| `status`     | int    | 状态码。   |
| `message`    | string | 返回信息。 |
| `reply_list` | array  | 回复列表。 |

- **200 OK**: 获取Reply列表成功。
- **404 Not Found**: 未找到指定的帖子或回复。
- **400 Bad Request**: 请求参数不合法。

若获取成功，则`reply_list`中的每个对象内容如下：

| 参数名                | 类型   | 描述              |
| --------------------- | ------ | ----------------- |
| `reply_id`            | int    | 回复ID。          |
| `reply_content`       | string | 回复内容。        |
| `replier_name`        | string | 回复者名字。      |
| `replier_profile_url` | string | 回复者头像的URL。 |
| `like_count`          | int    | 回复的点赞数。    |
| `publish_time`        | time   | 回复的发布时间。  |

---

### （5）删除Post

#### **url：`/index/post/delete`**

**POST `/post/delete`**

**描述：**
此接口用于删除指定的Post。

**请求参数：**

| 参数名    | 类型 | 必填 | 描述       |
| --------- | ---- | ---- | ---------- |
| `post_id` | int  | 是   | 帖子的id。 |

**响应参数：**

- **200 OK**: 帖子删除成功。
- **404 Not Found**: 未找到指定的帖子。

---

### （6）在Post下发表Reply，以及对reply进行回复

#### **url：`/index/reply/create`**

**POST `/reply/create`**

**描述：**
此接口用于在指定Post下发表回复。

**请求参数：**

| 参数名            | 类型   | 必填 | 描述              |
| ----------------- | ------ | ---- | ----------------- |
| `post_id`         | int    | 是   | 帖子的id。        |
| `reply_content`   | string | 是   | 回复内容。        |
| `parent_reply_id` | int    | 否   | 对reply进行回复。 |

**响应参数：**

| 参数名     | 类型   | 描述                                  |
| ---------- | ------ | ------------------------------------- |
| `status`   | int    | 状态码。                              |
| `message`  | string | 返回信息。                            |
| `reply_id` | int    | 若创建成功则返回reply的id，方便跳转。 |

- **201 Created**: 回复成功。
- **400 Bad Request**: 请求参数不完整或格式错误。

---

### （7）删除Reply

#### **url：`/index/reply/delete`**

**POST `/reply/delete`**

**描述：**
此接口用于删除指定的Reply。

**请求参数：**

| 参数名     | 类型 | 必填 | 描述       |
| ---------- | ---- | ---- | ---------- |
| `reply_id` | int  | 是   | 回复的id。 |

**响应参数：**

- **200 OK**: 回复删除成功。
- **404 Not Found**: 未找到指定的回复。

---

### （8）获取reply详情

#### **url：`/index/reply/detail`**

**GET `/reply/detail?reply_id=reply_id`**

**描述：**
此接口用于获取指定reply的详细信息。

**请求参数：**

| 参数名     | 类型 | 必填 | 描述       |
| ---------- | ---- | ---- | ---------- |
| `reply_id` | int  | 是   | 回复的id。 |

**响应参数：**

| 参数名         | 类型   | 描述       |
| -------------- | ------ | ---------- |
| `status`       | int    | 状态码。   |
| `message`      | string | 返回信息。 |
| `reply_detail` | list   | 回复详情。 |

- **200 OK**: 获取reply详情成功，返回详细信息。
- **404 Not Found**: 未找到指定的回复。
- **400 Bad Request**: 请求参数不合法。

若获取成功，则`reply_detail`的参数如下：

| 参数名                | 类型   | 描述              |
| --------------------- | ------ | ----------------- |
| `reply_id`            | int    | 回复id。          |
| `reply_content`       | string | 回复内容。        |
| `replier_name`        | string | 回复者名字。      |
| `replier_profile_url` | string | 回复者头像的url。 |
| `like_count`          | int    | 回复的点赞数。    |
| `publish_time`        | time   | 回复的发布时间。  |

---

## 5.课程板块

### （0）Course类与Score类

**Course类如下：**

```python
class Course(models.Model):
    COURSE_TYPE_CHOICES = [
        ('compulsory', 'Compulsory'),        # 必修课
        ('elective', 'Elective'),            # 选修课
        ('restricted_elective', 'Restricted Elective'),  # 限选课
    ]

    COURSE_METHOD_CHOICES = [
        ('online', 'Online'), # 线上
        ('offline', 'Offline'), # 线下
        ('hybrid', 'Hybrid'), # 混合
    ]

    id = models.AutoField(primary_key=True)  # 自增id, 自动设为主键
    course_name = models.CharField(max_length=255) # 课程名
    course_type = models.CharField(max_length=50, choices=COURSE_TYPE_CHOICES) # 课程类型
    college = models.CharField(max_length=255) # 开设大学
    credits = models.DecimalField(max_digits=4, decimal_places=2) # 学分
    course_teacher = models.CharField(max_length=255) # 课程老师
    course_method = models.CharField(max_length=50, choices=COURSE_METHOD_CHOICES) # 教学方式
    assessment_method = models.CharField(max_length=255) # 考核方式
    likes = GenericRelation(Like)
    score = models.DecimalField(max_digits=3, decimal_places=2, default=0.00) # 评分
    all_score = models.DecimalField(max_digits=3, decimal_places=2, default=0.00) # 总评分
    all_people = models.IntegerField(default=0) # 总评分人数
    relative_articles = models.ManyToManyField(Article, related_name='courses')
    publish_time = models.DateTimeField(auto_now_add=True)
```

**Score类如下：**//需要加上comment（内容），publish_time等内容做单独一个类

```python
class Score(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='scores')  # 使用 'scores' 作为反向查询名称
    score = models.DecimalField(max_digits=3, decimal_places=2)

    class Meta:
        unique_together = ('user', 'course')
```



---

### （1）创建Course

#### **url：`/index/course/create`**

**POST `/course/create`**

**描述：**
此接口用于创建新的课程。

**请求参数：**

| 参数名              | 类型    | 必填 | 描述                           |
| ------------------- | ------- | ---- | ------------------------------ |
| `course_name`       | string  | 是   | 课程名。                       |
| `course_type`       | string  | 是   | 课程类型（必修、选修、限选）。 |
| `college`           | string  | 是   | 开设该课程的学院。             |
| `campus`            | string  | 是   | 开设该课程的校区。             |
| `credits`           | decimal | 是   | 课程学分。                     |
| `course_teacher`    | string  | 是   | 课程教师。                     |
| `course_method`     | string  | 是   | 教学方式（线上、线下、混合）。 |
| `assessment_method` | string  | 是   | 考核方式。                     |

**响应参数：**

| 参数名      | 类型   | 描述       |
| ----------- | ------ | ---------- |
| `status`    | int    | 状态码。   |
| `message`   | string | 返回信息。 |
| `course_id` | int    | 课程id。   |

- **200 OK**: 课程创建成功。
- **400 Bad Request**: 请求参数不完整或格式错误。

---

### （2）编辑Course

#### **url：`/index/course/edit`**

**POST `/course/edit`**

**描述：**
此接口用于编辑已存在的课程。

**请求参数：**

| 参数名              | 类型    | 必填 | 描述                           |
| ------------------- | ------- | ---- | ------------------------------ |
| `id`                | int     | 是   | 课程ID。                       |
| `course_name`       | string  | 否   | 课程名。                       |
| `course_type`       | string  | 否   | 课程类型（必修、选修、限选）。 |
| `college`           | string  | 否   | 开设大学。                     |
| `credits`           | decimal | 否   | 课程学分。                     |
| `course_teacher`    | string  | 否   | 课程教师。                     |
| `course_method`     | string  | 否   | 教学方式（线上、线下、混合）。 |
| `assessment_method` | string  | 否   | 考核方式。                     |

**响应参数：**

- **200 OK**: 课程编辑成功。
- **404 Not Found**: 未找到指定的课程。
- **400 Bad Request**: 请求参数不合法。

---

### （3）删除Course

#### **url：`/index/course/delete`**

**POST `/course/delete`**

**描述：**
此接口用于删除指定的课程。

**请求参数：**

| 参数名      | 类型 | 必填 | 描述     |
| ----------- | ---- | ---- | -------- |
| `course_id` | int  | 是   | 课程ID。 |

**响应参数：**

- **200 OK**: 课程删除成功。
- **404 Not Found**: 未找到指定的课程。

---

###  （4）对课程评分并评价

// 也许可以考虑直接合并到“Course下发帖”，打分同时发表post
// 但“Course下发帖”发帖实际上承担的功能是提问吧，还是不合并了，正好和评分分开

#### **url：`/index/course/rate`**

**POST `/course/rate`**

**描述：**
此接口用于为课程打分并进行评价。

**请求参数：**

| 参数名      | 类型    | 必填 | 描述                   |
| ----------- | ------- | ---- | ---------------------- |
| `course_id` | int     | 是   | 课程ID。               |
| `score`     | decimal | 是   | 评分（0.00 到 5.00）。 |
| `comment`   | string  | 否   | 评价内容。             |

**响应参数：**

- **201 Created**: 评分和评价提交成功。
- **400 Bad Request**: 请求参数不完整或格式错误。
- **500  Internal Server Error**: 服务器内部错误。

---

### （5）修改课程评分或评价

#### **url：`/index/course/edit_rating`**

**POST `/course/edit_rating`**

**描述：**
此接口用于修改已提交的课程评分与评价。

**请求参数：**

| 参数名      | 类型    | 必填 | 描述                           |
| ----------- | ------- | ---- | ------------------------------ |
| `course_id` | int     | 是   | 课程ID。                       |
| `score`     | decimal | 否   | 修改后的评分（0.00 到 5.00）。 |
| `comment`   | string  | 否   | 修改后的评价内容。             |

**响应参数：**

- **200 OK**: 评分和评价修改成功。
- **404 Not Found**: 未找到指定的课程或尚未评分。
- **400 Bad Request**: 请求参数不合法。

---

### （6）获取某个用户对某个课程的评价

// 这个地方其实应该改成get吧？算了之后再改吧

#### **url：`/index/course/user_evaluation`**

**POST `/course/user_evaluation`**

**描述：**
此接口用于获取用户已提交的课程评分与评价。

**请求参数：**

| 参数名         | 类型 | 必填 | 描述     |
| -------------- | ---- | ---- | -------- |
| `user_id`      | int  | 是   | 用户ID。 |
| `course_id`    | int  | 是   | 课程ID。 |
| **响应参数：** |      |      |          |

| 参数名    | 类型    | 描述                       |
| --------- | ------- | -------------------------- |
| `status`  | int     | 状态码。                   |
| `message` | string  | 返回信息。                 |
| `score`   | decimal | 用户评分（0.00 到 5.00）。 |
| `comment` | string  | 用户的评价内容。           |

- **200 OK**: 评分和评价修改成功。
- **401 Unauthorized**: 用户未登陆或无权获得他人评价；
- **404 Not Found**: 未找到指定的课程评分或评价。
- **400 Bad Request**: 请求参数不合法。

### （7）通过id获取Course的详细信息

#### **url：`/index/course/detail`**

**GET `/course/detail?course_id=course_id`**

**请求参数：**

| 参数名      | 类型 | 必填 | 描述       |
| ----------- | ---- | ---- | ---------- |
| `course_id` | int  | 是   | 课程的id。 |

**响应参数：**

| 参数名          | 类型   | 描述       |
| --------------- | ------ | ---------- |
| `status`        | int    | 状态码。   |
| `message`       | string | 返回信息。 |
| `course_detail` | list   | 课程详情。 |

- **200 OK**: 获取课程详情成功，返回详细信息。
- **404 Not Found**: 未找到指定的课程。
- **400 Bad Request**: 请求参数不合法。

若获取成功，则`course_detail`内容如下：

| 参数名              | 类型    | 描述                           |
| ------------------- | ------- | ------------------------------ |
| `course_id`         | int     | 课程id。                       |
| `course_name`       | string  | 课程名。                       |
| `course_type`       | string  | 课程类型（必修、选修、限选）。 |
| `college`           | string  | 专业开设学院。                 |
| `campus`            | string  | 专业开设校区。                 |
| `credits`           | decimal | 学分。                         |
| `course_teacher`    | string  | 教师名称。                     |
| `course_method`     | string  | 教学方式（线上、线下、混合）。 |
| `assessment_method` | string  | 考核方式。                     |
| `score`             | decimal | 评分（0.00 到 5.00）。         |
| `all_score`         | decimal | 总评分。                       |
| `all_people`        | int     | 总评分人数。                   |
| `relative_articles` | array   | 相关的文章列表。               |
| `publish_time`      | time    | 课程发布的时间。               |

---

### （8）根据id分页获取Course下的Post列表

#### **url：`/index/course/post_list`**

**GET `/course/post_list?course_id=course_id&page_index=page_index&page_size=page_size`**

**描述：**
此接口用于获取指定课程（通过课程ID）下，按分页要求返回的Post列表。

**请求参数：**

| 参数名       | 类型 | 必填 | 描述                           |
| ------------ | ---- | ---- | ------------------------------ |
| `course_id`  | int  | 是   | 课程ID。                       |
| `page_index` | int  | 否   | 第几页，默认为第一页。         |
| `page_size`  | int  | 否   | 每页显示的Post数量，默认为20。 |

**响应参数：**

| 参数名      | 类型   | 描述       |
| ----------- | ------ | ---------- |
| `status`    | int    | 状态码。   |
| `message`   | string | 返回信息。 |
| `post_list` | array  | Post列表。 |

- **200 OK**: 获取Post列表成功。
- **500 Internal Server Error**: 服务器内部错误。

若获取成功，则`post_list`中的每个Post对象的内容如下：

| 参数名               | 类型   | 描述             |
| -------------------- | ------ | ---------------- |
| `post_id`            | int    | 帖子ID。         |
| `post_title`         | string | 帖子标题。       |
| `post_content`       | string | 帖子内容。       |
| `poster_name`        | string | 发帖人名称。     |
| `poster_profile_url` | string | 发帖人头像URL。  |
| `view_count`         | int    | 帖子的浏览量。   |
| `like_count`         | int    | 帖子的点赞数。   |
| `reply_count`        | int    | 帖子的回复数。   |
| `tags`               | array  | 帖子的标签。     |
| `publish_time`       | time   | 帖子的发布时间。 |

---

### （9）根据id分页获取Course下的评分列表

#### **url：`/index/course/score_list`**

**GET `/course/score_list?course_id=course_id&page_index=page_index&page_size=page_size`**

**描述：**
此接口用于获取指定课程（通过课程ID）下，按分页要求返回的socre_list列表，即coursereview。

**请求参数：**

| 参数名       | 类型 | 必填 | 描述                           |
| ------------ | ---- | ---- | ------------------------------ |
| `course_id`  | int  | 是   | 课程ID。                       |
| `page_index` | int  | 否   | 第几页，默认为第一页。         |
| `page_size`  | int  | 否   | 每页显示的post数量，默认为20。 |

**响应参数：**

| 参数名       | 类型   | 描述        |
| ------------ | ------ | ----------- |
| `status`     | int    | 状态码。    |
| `message`    | string | 返回信息。  |
| `score_list` | array  | score列表。 |

- **200 OK**: 获取Score列表成功。
- **500 Internal Server Error**: 服务器内部错误。

若获取成功，则`score_list`中的每个Post对象的内容如下：

//你来补全

### （10）分页获取course列表

#### **url：`/index/course/list`**

**GET `/course/list?page_index=page_index&page_size=page_size`**

**描述：**
此接口用于提交分页要求，并获取course列表的对应页。

**请求参数：**

| 参数名       | 类型 | 必填 | 描述                       |
| ------------ | ---- | ---- | -------------------------- |
| `page_index` | int  | 否   | 第几页，无此字段默认⾸⻚   |
| `page_size`  | int  | 否   | 每⻚项⽬数，⽆此字段默认20 |

**响应参数：**

| 参数名        | 类型   | 描述       |
| ------------- | ------ | ---------- |
| `status`      | int    | 状态码。   |
| `message`     | string | 返回信息。 |
| `course_list` | array  | post列表。 |

- **200 OK**: 获取课程列表成功。

- **500 Internal Server Error**: 服务器内部错误；

若获取成功，则`course_list`中的每个list对象的内容如下：

| 参数名              | 类型    | 描述                           |
| ------------------- | ------- | ------------------------------ |
| `course_id`         | int     | 课程id。                       |
| `course_name`       | string  | 课程名。                       |
| `course_type`       | string  | 课程类型（必修、选修、限选）。 |
| `college`           | string  | 开设学院。                     |
| `credits`           | decimal | 学分。                         |
| `course_teacher`    | string  | 教师名称。                     |
| `course_method`     | string  | 教学方式（线上、线下、混合）。 |
| `assessment_method` | string  | 考核方式。                     |
| `score`             | decimal | 评分（0.00 到 5.00）。         |
| `all_score`         | decimal | 总评分。                       |
| `all_people`        | int     | 总评分人数。                   |
| `relative_articles` | array   | 相关的文章列表。               |
| `publish_time`      | time    | 课程发布的时间。               |

---

## 7.私信板块

### （0）私信类

```python
class Message(models.Model):
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)  # 发送者
    receiver = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE)  # 接收者
    content = models.TextField()  # 消息内容
    sent_at = models.DateTimeField(auto_now_add=True)  # 发送时间
    read = models.BooleanField(default=False)  # 消息是否已读
    is_deleted_by_sender = models.BooleanField(default=False)  # 发送者是否已删除
    is_deleted_by_receiver = models.BooleanField(default=False)  # 接收者是否已删除

    class Meta:
        ordering = ['-sent_at']  # 按时间倒序排列

    def __str__(self):
        return f"From {self.sender.username} to {self.receiver.username}: {self.content[:20]}"

```

### （1）发送私信

#### **url：`/index/messages/send`**

**POST `/message/send`**

**描述：**
 此接口用于发送一条私信。

**请求参数：**

| 参数名        | 类型   | 必填 | 描述             |
| ------------- | ------ | ---- | ---------------- |
| `receiver_id` | int    | 是   | 接收者的用户ID。 |
| `content`     | string | 是   | 私信内容。       |

**响应参数：**

| 参数名       | 类型   | 描述       |
| ------------ | ------ | ---------- |
| `status`     | int    | 状态码。   |
| `message`    | string | 返回信息。 |
| `message_id` | int    | 消息id。   |

- **200 OK**: 私信发送成功；
- **404 Not Found**: 接收者用户未找到；
- **400 Bad Request**: 请求参数错误；
- **500 Internal Server Error**: 服务器内部错误；

#### （2）获取私信列表

#### **url：`index/messages/list`**

**GET `/list?page_size=page_size&page_index=page_index`**

**描述：**
 此接口用于获取当前用户的私信列表，包括发件人、内容、发送时间等信息。

**请求参数：**

| 参数名       | 类型 | 必填 | 描述                           |
| ------------ | ---- | ---- | ------------------------------ |
| `page_size`  | int  | 否   | 每页返回的消息数量，默认10条。 |
| `page_index` | int  | 否   | 第几页，默认第一页。           |

**响应参数：**

| 参数名         | 类型   | 描述                               |
| -------------- | ------ | ---------------------------------- |
| `status`       | int    | 状态码。                           |
| `message`      | string | 返回信息。                         |
| `message_list` | array  | 消息列表，包含每条消息的详细信息。 |


- **200 OK**: 获取消息列表成功；

- **404 Not Found**: 用户未找到或没有任何消息；

- **500 Internal Server Error**: 服务器内部错误；

**若获取成功，则 `message_list` 的内容如下：**

| 参数名        | 类型   | 描述           |
| ------------- | ------ | -------------- |
| `sender_id`   | int    | 发送者用户ID。 |
| `receiver_id` | int    | 接收者用户ID。 |
| `content`     | string | 消息内容。     |
| `sent_at`     | time   | 发送时间。     |
| `read`        | bool   | 消息是否已读。 |


#### （3）标记消息为已读

#### **url：`index/messages/read`**

**POST `/message/read`**

**描述：**
 此接口用于标记一条消息为已读。

**请求参数：**

| 参数名       | 类型 | 必填 | 描述       |
| ------------ | ---- | ---- | ---------- |
| `message_id` | int  | 是   | 消息的ID。 |

**响应参数：**

- **200 OK**: 消息标记为已读成功；
- **404 Not Found**: 消息未找到；
- **500 Internal Server Error**: 服务器内部错误；

#### （4）撤回私信

#### **url：`index/messages/delete`**

**POST `/message/delete`**

**描述：**
 此接口用于发送者撤回私信，有时间限制。

**请求参数：**

| 参数名       | 类型 | 必填 | 描述       |
| ------------ | ---- | ---- | ---------- |
| `message_id` | int  | 是   | 消息的ID。 |

**响应参数：**

- **200 OK**: 删除成功；
- **403 Forbidden**: 当前用户无权删除此消息；
- **404 Not Found**: 消息未找到；
- **500 Internal Server Error**: 服务器内部错误；


## 8.通知板块

###  （0）通知类

```python
class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    def __str__(self):
        return f"Notification for {self.user.username} - {self.message[:20]}"

    class Meta:
        ordering = ['-created_at']
```

### （1）发送通知

搞成钩子函数了

### （2）获取通知列表

#### **url：`index/notifications/list`**

**GET /`notifications/list?page_size=page_size&page_index=page_index`**

**描述：**  
此接口用于获取当前用户的通知列表。

**请求参数：**

| 参数名       | 类型 | 必填 | 描述                           |
| ------------ | ---- | ---- | ------------------------------ |
| `page_size`  | int  | 否   | 每页返回的通知数量，默认10条。 |
| `page_index` | int  | 否   | 第几页，默认第一页。           |

**响应参数：**

| 参数名              | 类型   | 描述                               |
| ------------------- | ------ | ---------------------------------- |
| `status`            | int    | 状态码。                           |
| `message`           | string | 返回信息。                         |
| `notification_list` | array  | 通知列表，包含每条通知的详细信息。 |
| `total`             | int    | 总通知数。                         |
| `unread_count`      | int    | 未读通知数。                       |

- **200 OK**: 获取通知列表成功；
- **401 Unauthorized**: 用户未登陆或无权获得他人通知列表；
- **404 Not Found**: 用户未找到或没有任何通知；
- **500 Internal Server Error**: 服务器内部错误；

**若获取成功，则 `notification_list` 的内容如下：**

| 参数名            | 类型   | 描述                                                         |
| ----------------- | ------ | ------------------------------------------------------------ |
| `notification_id` | int    | 通知ID。                                                     |
| `type`            | string | 通知类型，`post for your article`，`reply for your post`，`reply for your reply`，`private message`。 |
| `message`         | string | 通知内容。                                                   |
| `created_at`      | time   | 通知创建时间。                                               |
| `is_read`         | bool   | 通知是否已读。                                               |
| `extra`           | list   | 可能需要的额外信息，测试用。                                 |
| `related_object`  | list   | 通知关联的对象。                                             |

其中，`extra`内容如下：
| 参数名      | 类型   | 描述               |
| ----------- | ------ | ------------------ |
| `user_name` | string | 通知对象的用户名。 |

`related_object`内容如下：

| 参数名    | 类型   | 描述                                                    |
| --------- | ------ | ------------------------------------------------------- |
| `type`    | string | 关联对象的类型，`post`，`message`，`article`，`reply`。 |
| `id`      | int    | 关联对象id。                                            |
| `preview` | string | 内容预览。                                              |


### （3）标记通知为已读

#### **url：`/notifications/read`**

**POST `/read`**

**描述：**  
此接口用于标记一条通知为已读。

**请求参数：**

| 参数名            | 类型 | 必填 | 描述                     |
| ----------------- | ---- | ---- | ------------------------ |
| `notification_id` | int  | 是   | 通知的ID，用于标记已读。 |

**响应参数：**

- **200 OK**: 通知标记为已读成功；
- **404 Not Found**: 通知未找到；
- **500 Internal Server Error**: 服务器内部错误；

------

## 9. 收藏夹板块

### （0）Star类

```python
class StarFolder(MPTTModel):
    """支持多级嵌套的收藏夹"""
    name = models.CharField(max_length=100, verbose_name="收藏夹名称")
    user = models.ForeignKey(
        'User', 
        on_delete=models.CASCADE,
        related_name='star_folders',
        verbose_name="所属用户"
    )
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="父级收藏夹"
    )
    is_default = models.BooleanField(default=False, verbose_name="默认收藏夹")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    cover = models.URLField(null=True, blank=True, verbose_name="封面图URL")
    description = models.TextField(null=True, blank=True, verbose_name="描述")

    class MPTTMeta:
        order_insertion_by = ['name']
    
    class Meta:
        verbose_name = "收藏夹"
        verbose_name_plural = "收藏夹"
        unique_together = ('user', 'name')  # 同一用户下收藏夹名称唯一
        indexes = [
            models.Index(fields=['user', 'is_default']),
        ]

    def __str__(self):
        return f"{self.user.username}的收藏夹：{self.name}"

class Star(models.Model):
    """支持多级收藏夹的泛型收藏模型"""
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='stars',
        verbose_name="用户",
        db_index=True
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name="内容类型"
    )
    object_id = models.PositiveIntegerField(verbose_name="对象ID")
    content_object = GenericForeignKey('content_type', 'object_id')
    
    folder = models.ForeignKey(
        StarFolder,
        on_delete=models.CASCADE,
        related_name='stars',
        verbose_name="所属收藏夹"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="收藏时间")
    notes = models.TextField(null=True, blank=True, verbose_name="收藏备注")

    class Meta:
        verbose_name = "收藏记录"
        verbose_name_plural = "收藏记录"
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['-created_at']),
        ]
        constraints = [
            # 同一用户不能在同一个收藏夹重复收藏相同内容
            models.UniqueConstraint(
                fields=['user', 'content_type', 'object_id', 'folder'],
                name='unique_star_per_folder'
            ),
        ]

    def __str__(self):
        return f"{self.user.username}收藏的{self.content_object}"

    def save(self, *args, **kwargs):
        # 自动关联默认收藏夹
        if not self.folder_id:
            default_folder = StarFolder.objects.get_or_create(
                user=self.user,
                is_default=True,
                defaults={'name': '默认收藏'}
            )[0]
            self.folder = default_folder
        super().save(*args, **kwargs)

    @classmethod
    def get_star_count(cls, obj):
        """获取对象的收藏计数（带缓存）"""
        ct = ContentType.objects.get_for_model(obj)
        cache_key = f'star_count:{ct.id}:{obj.id}'
        count = cache.get(cache_key)
        if count is None:
            count = cls.objects.filter(content_type=ct, object_id=obj.id).count()
            cache.set(cache_key, count, timeout=300)
        return count

```

### （1）收藏Course/Article/Post

#### **url：`/index/star`**

**POST `/star`**

**描述：**
 此接口用于用户收藏课程、文章或帖子，并选择收藏夹。若未选择收藏夹，则默认为默认收藏夹。

**请求参数：**

| 参数名         | 类型   | 必填 | 描述                                     |
| -------------- | ------ | ---- | ---------------------------------------- |
| `content_type` | int | 是   | 收藏内容的类型：0/1/2分别表示课程、文章、帖子        |
| `content_id`   | int    | 是   | 收藏内容的ID，课程ID、文章ID或帖子ID     |
| `folder_id`    | int    | 否   | 选择的收藏夹ID，若为空则收藏至默认收藏夹 |

**响应参数：**

- **200 OK**: 收藏成功
- **409 Conflict**: 已经收藏过该内容
- **404 Not Found**: 未找到指定内容
- **500 Internal Server Error**: 服务器内部错误

------

### （2）创建收藏夹

#### **url：`/index/star/create`**

**POST `/star/create`**

**描述：**
 此接口用于用户创建一个新的收藏夹。

**请求参数：**

| 参数名        | 类型   | 必填 | 描述                 |
| ------------- | ------ | ---- | -------------------- |
| `folder_name` | string | 是   | 收藏夹名称，同一用户的收藏夹不能重名 |
| `description` | string | 否   | 收藏夹的描述（可选） |

**响应参数：**

| 参数名      | 类型   | 描述             |
| ----------- | ------ | ---------------- |
| `status`    | int    | 状态码           |
| `message`   | string | 返回信息         |
| `folder_id` | int    | 若创建成功则返回 |

- **200 OK**: 创建收藏夹成功
- **400 Bad Request**: 请求参数错误或缺失
- **500 Internal Server Error**: 服务器内部错误

------

### （3）获取收藏列表

#### **url：`/index/star/list`**

**GET `/star/list?folder_id=folder_id`**

**描述：**
 此接口用于获取当前用户的所有收藏内容，支持选择获取某个特定收藏夹下的内容。若未选择收藏夹，则返回所有收藏内容。

**请求参数：**

| 参数名      | 类型 | 必填 | 描述                                   |
| ----------- | ---- | ---- | -------------------------------------- |
| `folder_id` | int  | 是   | 收藏夹ID，若为空则返回所有收藏夹的内容 |

**响应参数：**

| 参数名      | 类型   | 描述           |
| ----------- | ------ | -------------- |
| `status`    | int    | 状态码         |
| `message`   | string | 返回信息       |
| `star_list` | array  | 收藏的内容列表 |

- **200 OK**: 获取收藏列表成功
- **404 Not Found**: 用户未收藏任何内容
- **500 Internal Server Error**: 服务器内部错误

**若获取成功，则 `star_list` 的内容如下：**

| 参数名         | 类型   | 描述                               |
| -------------- | ------ | ---------------------------------- |
| `content_type` | int | 收藏内容的类型：0/1/2分别表示课程、文章、帖子 |
| `content_id`   | int    | 收藏内容的ID                       |
| `content_name` | string | 内容的名称（如课程名、文章标题等） |
| `created_at`   | time   | 收藏时间                           |

------

### （4）取消收藏

#### **url：`/index/unstar`**

**POST `/unstar`**

**描述：**
 此接口用于用户取消收藏课程、文章或帖子。

**请求参数：**

| 参数名         | 类型   | 必填 | 描述                                 |
| -------------- | ------ | ---- | ------------------------------------|
| `content_type` | int | 是   | 收藏内容的类型：0/1/2分别表示课程、文章、帖子 |
| `content_id`   | int    | 是   | 收藏内容的ID，课程ID、文章ID或帖子ID |

**响应参数：**

- **200 OK**: 取消收藏成功
- **404 Not Found**: 未找到收藏内容
- **500 Internal Server Error**: 服务器内部错误

### （5）获取收藏夹列表

#### **url：`/index/star/folder/list`**

**GET `/star/folder/list`**

**描述：**  
此接口用于获取当前用户的所有收藏夹信息，返回每个收藏夹的基本信息以及其中的收藏内容。

**请求参数：**

无

**响应参数：**

| 参数名    | 类型   | 描述       |
| --------- | ------ | ---------- |
| `status`  | int    | 状态码     |
| `message` | string | 返回信息   |
| `folders` | list   | 收藏夹列表 |

- **200 OK**: 获取收藏夹信息成功
- **404 Not Found**: 用户未创建任何收藏夹
- **500 Internal Server Error**: 服务器内部错误

若获取成功，则 `folders` 的内容如下：

| 参数名        | 类型     | 描述               |
| ------------- | -------- | ------------------ |
| `folder_id`   | int      | 收藏夹ID           |
| `folder_name` | string   | 收藏夹名称         |
| `description` | string   | 收藏夹描述（可选） |
| `star_count`  | int      | 收藏夹内的内容数量 |
| `created_at`  | datetime | 收藏夹创建时间     |

---

## 10.点赞板块

### （0）Like类

```python
class Like(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='likes')  # 点赞用户
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)  # 点赞内容的类型（文章、帖子或回复）
    object_id = models.PositiveIntegerField()  # 点赞内容的ID
    content_object = GenericForeignKey('content_type', 'object_id')  # 泛型关联字段

    created_at = models.DateTimeField(auto_now_add=True)  # 点赞时间

    class Meta:
        unique_together = ('user', 'content_type', 'object_id')  # 确保同一个用户只能对同一内容点赞一次
```

### （1）为article/post/reply点赞

#### **url：`index/like`**

**POST `/like`**

**描述：**
 此接口用于给文章、帖子或回复点赞。

**请求参数：**

| 参数名         | 类型 | 必填 | 描述                                                   |
| -------------- | ---- | ---- | ------------------------------------------------------ |
| `content_type` | int  | 是   | 内容类型，0/1/2分别对应 `article`、`post` 、 `reply`。 |
| `content_id`   | int  | 是   | 文章、帖子或回复的ID。                                 |

**响应参数：**

| 参数名    | 类型   | 描述     |
| --------- | ------ | -------- |
| `status`  | int    | 状态码   |
| `message` | string | 返回信息 |

**状态码说明：**

- **200 OK**: 点赞成功。
- **400 Bad Request**: 参数错误。
- **404 Not Found**: 找不到对应的内容。
- **409 Conflict**: 用户已经点赞过该内容。
- **500 Internal Server Error**: 服务器内部错误。

### （2）取消点赞

#### **url：`index/unlike`**

**POST `/unlike`**

**描述：**
 此接口用于取消点赞。

**请求参数：**

| 参数名         | 类型 | 必填 | 描述                                                   |
| -------------- | ---- | ---- | ------------------------------------------------------ |
| `content_type` | int  | 是   | 内容类型，0/1/2分别对应 `article`、`post` 、 `reply`。 |
| `content_id`   | int  | 是   | 文章、帖子或回复的ID。                                 |

**响应参数：**

| 参数名    | 类型   | 描述     |
| --------- | ------ | -------- |
| `status`  | int    | 状态码   |
| `message` | string | 返回信息 |

**状态码说明：**

- **200 OK**: 取消点赞成功。
- **400 Bad Request**: 参数错误。
- **404 Not Found**: 找不到对应的内容。
- **500 Internal Server Error**: 服务器内部错误。

### （3）获取内容的点赞数

#### **url：`index/like/count`**

**GET `/like/count?content_type=content_type&content_id=content_id`**

**描述：**
 此接口用于获取文章、帖子或回复的点赞数。无需身份令牌。

**请求参数：**

| 参数名         | 类型 | 必填 | 描述                                                   |
| -------------- | ---- | ---- | ------------------------------------------------------ |
| `content_type` | int  | 是   | 内容类型，0/1/2分别对应 `article`、`post` 、 `reply`。 |
| `content_id`   | int  | 是   | 文章、帖子或回复的ID。                                 |

**响应参数：**

| 参数名       | 类型   | 描述     |
| ------------ | ------ | -------- |
| `like_count` | int    | 点赞数   |
| `status`     | int    | 状态码   |
| `message`    | string | 返回信息 |

**状态码说明：**

- **200 OK**: 获取点赞数成功。
- **404 Not Found**: 找不到对应的内容。
- **500 Internal Server Error**: 服务器内部错误。

### （4）获取用户点赞的内容列表

#### **url：`index/like/user`**

**GET `/like/user?user_id=user_id&page_size=page_size&page_index=page_index`**

**描述：**
 此接口用于获取某个用户点赞过的所有内容列表。

**请求参数：**

| 参数名       | 类型 | 必填 | 描述                           |
| ------------ | ---- | ---- | ------------------------------ |
| `user_id`    | int  | 是   | 用户ID。                       |
| `page_size`  | int  | 否   | 每页返回的内容数量，默认为20。 |
| `page_index` | int  | 否   | 第几页，默认第一页。           |

**响应参数：**

| 参数名         | 类型   | 描述                               |
| -------------- | ------ | ---------------------------------- |
| `status`       | int    | 状态码                             |
| `message`      | string | 返回信息                           |
| `content_list` | array  | 点赞内容的列表，包含内容类型和ID。 |

- **200 OK**: 获取用户点赞内容列表成功。
- **404 Not Found**: 用户未点赞任何内容。
- **500 Internal Server Error**: 服务器内部错误。

**若获取成功，则 `content_list` 的内容如下：**

| 参数名         | 类型 | 描述       |
| -------------- | ---- | ---------- |
| `content_type` | int  | 是         |
| `content_id`   | int  | 内容的ID。 |

------



## 11.图片API板块

//确实需要前端压缩一下

### （0）Image类

```python
class Image(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='images')  # 上传图片的用户
    image = models.ImageField(upload_to='user_images/')  # 图片文件
    created_at = models.DateTimeField(auto_now_add=True)  # 上传时间

    def __str__(self):
        return f"Image by {self.user.username} at {self.created_at}"
```

### （1）上传头像

#### **url：`/index/image/profile`**

**POST `/image/profile`**

**描述：**
 此接口用于上传用户头像，上传成功后将返回一个图片的URL。

**请求参数：**

| 参数名  | 类型 | 必填 | 描述               |
| ------- | ---- | ---- | ------------------ |
| `image` | file | 是   | 用户头像图片文件。 |

**响应参数：**

| 参数名        | 类型   | 描述                                                         |
| ------------- | ------ | ------------------------------------------------------------ |
| `status`      | int    | 状态码                                                       |
| `message`     | string | 返回信息                                                     |
| `profile_url` | string | 返回挂载头像图片的URL地址（形如`GET /image/profile?user_name=user_name`） |

**状态码说明：**

- **200 OK**: 上传头像成功，返回头像URL。
- **400 Bad Request**: 上传的文件格式不支持或文件过大。
- **500 Internal Server Error**: 服务器错误，上传失败。

------

### （2）获取用户头像

#### **url：`/index/image/user`**

**GET `/image/user?user_id=user_id`**

**描述：**
 此接口用于获取指定用户的头像，若用户没有头像，则返回默认头像。

**请求参数：**

| 参数名    | 类型 | 必填 | 描述   |
| --------- | ---- | ---- | ------ |
| `user_id` | int  | 是   | 用户id |

**响应参数：**

| 参数名    | 类型   | 描述     |
| --------- | ------ | -------- |
| `status`  | int    | 状态码   |
| `message` | string | 返回信息 |
| `image`   | image  | 返回图片 |

**状态码说明：**

- **200 OK**: 成功获取头像，返回头像URL。
- **404 Not Found**: 用户头像未找到，可能用户尚未上传头像。
- **500 Internal Server Error**: 服务器错误，获取头像失败。

------

### （3）在文章中上传图片

#### **url：`/index/image/article`**

**POST `/image/article`**

**描述：**
 此接口用于在文章中上传图片，上传成功后将返回一个图片的URL，用户可将该URL嵌入文章内容中。

**请求参数：**

| 参数名  | 类型 | 必填 | 描述           |
| ------- | ---- | ---- | -------------- |
| `image` | file | 是   | 文章图片文件。 |

**响应参数：**

| 参数名      | 类型   | 描述                  |
| ----------- | ------ | --------------------- |
| `status`    | int    | 状态码                |
| `message`   | string | 返回信息              |
| `image_url` | string | 返回图片的访问URL地址 |

**状态码说明：**

- **200 OK**: 图片上传成功，返回图片URL。
- **400 Bad Request**: 上传的文件格式不支持或文件过大。
- **500 Internal Server Error**: 服务器内部错误。



### （4）根据url get图片

#### **url：`/index/image/get/<image_name>`**

**GET `/image/get/<image_name>`**

**描述：**
 此接口用于获取图片,实际上相当于对图片文件进行一个挂载，在文章中上传图片返回的url即是该api格式的

**请求参数：**

无

**响应参数：**

| 参数名    | 类型   | 描述     |
| --------- | ------ | -------- |
| `status`  | int    | 状态码   |
| `message` | string | 返回信息 |
| `image`   | file   | 返回图片 |

**状态码说明：**

- **200 OK**: 获取成功，返回图片。
- **500 Internal Server Error**: 服务器内部错误。



---

## 12. 资源API板块

### （0）Resource类

```python
def resource_upload_path(instance, filename):
    return f"resources/{uuid.uuid4().hex[:8]}/{filename}"

class Resource(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='resources'
    )
    article = models.ForeignKey(
        'Article',  # 假设存在Article模型
        on_delete=models.CASCADE,
        related_name='resources'
    )
    file = models.FileField(
        upload_to=resource_upload_path,
        validators=[
            FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'zip', 'rar'])
        ],
        verbose_name='资源文件'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    file_size = models.PositiveIntegerField(editable=False)
    file_type = models.CharField(max_length=20, editable=False)
    download_count = models.PositiveIntegerField(default=0, verbose_name='下载次数')

    @property
    def filename(self):
        return self.file.name.split('/')[-1]

    def save(self, *args, **kwargs):
        self.file_size = self.file.size
        self.file_type = self.file.name.split('.')[-1].lower()
        super().save(*args, **kwargs)
```



### （1）上传资源

#### **url: `/index/resource/upload/`**

**POST `/resource/upload`**

**描述：**
 此接口用于上传资源文件，上传成功后返回一个下载用的 `source_url`，该 URL 将保存在 `Article` 对象的 `source_url` 字段中。

**请求参数：**

| 参数名       | 类型 | 必填 | 描述            |
| ------------ | ---- | ---- | --------------- |
| `file`       | file | 是   | 资源文件。      |
| `article_id` | int  | 是   | 关联的文章 ID。 |

**响应参数：**

| 参数名       | 类型   | 描述                 |
| ------------ | ------ | -------------------- |
| `status`     | int    | 状态码               |
| `message`    | string | 返回信息             |
| `source_url` | string | 返回资源的下载 URL。 |

**状态码说明：**

- **200 OK**: 资源上传成功，返回下载 URL。
- **400 Bad Request**: 文件格式不支持或文件过大。
- **404 Not Found**: 关联的文章 ID 不存在。
- **500 Internal Server Error**: 服务器内部错误。

---

### （2）资源下载

#### **url: `source_url`**

**GET `source_url`**

**描述：**
 此接口用于下载资源文件。通过 `source_url` 获取资源文件并返回给客户端。

**请求参数：**

无，但`login_required`

**响应参数：**

| 参数名    | 类型   | 描述           |
| --------- | ------ | -------------- |
| `status`  | int    | 状态码         |
| `message` | string | 返回信息       |
| `file`    | file   | 返回资源文件。 |

**状态码说明：**

- **200 OK**: 成功返回资源文件。
- **404 Not Found**: 资源文件未找到。
- **500 Internal Server Error**: 服务器内部错误。

---



## 13. 封禁与屏蔽管理API板块

### （1）封禁用户

#### **url: `/index/admin/block/user/`**

**POST `/admin/block/user`**

**接口描述：**
 管理员及以上权限封禁用户（需记录操作日志，或者直接搞个表记录），被封禁需立即执行一次登出操作？之后改吧

**请求参数：**

| 参数名    | 类型 | 必填 | 描述                                   |
| --------- | ---- | ---- | -------------------------------------- |
| `user_id` | int  | 是   | 要封禁的用户ID                         |
| `days`    | int  | 是   | 封禁天数（1-90天，超过90视作永久封禁） |

**响应参数：**

- **200 OK**: 封禁成功
- **400 Bad Request**: 参数错误/不能操作自己
- **403 Forbidden**: 无操作权限
- **404 Not Found**: 目标用户不存在
- **500 Internal Server Error**: 服务器内部错误

---

### （2）解禁用户

#### **url: `/index/admin/unblock/user/`**

**POST `/admin/unblock/user`**

**接口描述：**
 超级管理员解禁用户（需记录操作日志）

**请求参数：**

| 参数名    | 类型 | 必填 | 描述           |
| --------- | ---- | ---- | -------------- |
| `user_id` | int  | 是   | 要解禁的用户ID |

**响应参数：**（同上）

**状态码说明：**

- **200 OK**: 解禁成功
- **400 Bad Request**: 用户未被封禁
- **403 Forbidden**: 仅限超级管理员操作
- **404 Not Found**: 目标用户不存在

---

### （3）文章屏蔽管理

#### **url: `/index/admin/article/action/`**

**POST `/admin/article/action`**

**接口描述：**
 管理员屏蔽文章，超级管理员可删除/屏蔽

**请求参数：**

| 参数名       | 类型   | 必填 | 描述                     |
| ------------ | ------ | ---- | ------------------------ |
| `article_id` | int    | 是   | 操作的文章ID             |
| `action`     | string | 是   | 操作类型（block/delete） |

**响应参数：**


- **200 OK**: 操作成功
- **400 Bad Request**: 无效操作类型
- **403 Forbidden**: 无操作权限
- **404 Not Found**: 文章不存在

---

### （4）获取封禁用户列表

#### **url: `/index/admin/blocked-users/`**

**GET `/admin/blocked-users?page=1&size=20`**

**接口描述：**
 管理员及以上权限查看被封禁用户列表

**请求参数：**

| 参数名       | 类型 | 必填 | 描述               |
| ------------ | ---- | ---- | ------------------ |
| `page_index` | int  | 否   | 页码（默认1）      |
| `page_size`  | int  | 否   | 每页数量（默认20） |

**响应参数：**

| 参数名      | 类型   | 描述         |
| ----------- | ------ | ------------ |
| `status`    | int    | 状态码       |
| `message`   | string | 返回信息     |
| `user_num`  | int    | 总封禁用户数 |
| `user_list` | array  | 用户对象数组 |

若获取成功，则`user_list`内容如下：

| 参数名           | 类型   | 描述                 |
| ---------------- | ------ | -------------------- |
| `id`             | int    | 用户ID               |
| `username`       | string | 用户名               |
| `block_end_time` | string | 封禁截止时间         |
| `operator`       | string | 操作者用户名         |
| `block_reason`   | string | 封禁原因（预留字段） |

**状态码说明：**

- **200 OK**: 获取成功
- **403 Forbidden**: 无查看权限
- **500 Internal Server Error**: 服务器内部错误

---


前端优化：

1. 封禁操作二次确认弹窗
2. 封禁用户列表的自动刷新
3. 封禁剩余时间倒计时显示（考虑封禁直接不能登录？）
4. 操作日志审计界面（这个不急）

---

## 14.搜索功能

前面的写完了再优化



## 15.权限设置

大概就是超级管理员和管理员的设置，超级管理员出于安全考虑只能在数据库层面操作；

超级管理员能设置普通用户为管理员；然后封禁解封之类的。

### （1）提升用户为管理员

#### **url: `/index/admin/promote/`**

**POST `/admin/promote`**

**描述：**
 超级管理员将普通用户提升为管理员（仅限super_master操作）

**请求参数：**

| 参数名    | 类型 | 必填 | 描述           |
| --------- | ---- | ---- | -------------- |
| `user_id` | int  | 是   | 要提升的用户ID |

**响应参数：**

- **200 OK**: 提升成功
- **400 Bad Request**: 参数错误或用户已是管理员
- **403 Forbidden**: 无操作权限
- **404 Not Found**: 目标用户不存在
- **500 Internal Server Error**: 服务器内部错误

---

### （2）撤销管理员权限

#### **url: `/index/admin/demote/`**

**POST `/admin/demote`**

**描述：**
 超级管理员将管理员降级为普通用户（不能操作其他super_master）

**请求参数：**

| 参数名    | 类型 | 必填 | 描述               |
| --------- | ---- | ---- | ------------------ |
| `user_id` | int  | 是   | 要撤销权限的用户ID |

**响应参数：**

- **200 OK**: 撤销成功
- **400 Bad Request**: 参数错误或用户不是管理员
- **403 Forbidden**: 无操作权限/不能操作超级管理员
- **404 Not Found**: 目标用户不存在
- **500 Internal Server Error**: 服务器内部错误

---

### （3）分页获取用户列表（管理员权限）

#### **url: `/index/admin/users/`**

**GET `/admin/users?page=1&size=20`**

**描述：**
 管理员及以上权限查看用户列表（不同权限返回不同字段）

**请求参数：**

| 参数名       | 类型 | 必填 | 描述                   |
| ------------ | ---- | ---- | ---------------------- |
| `page_size`  | int  | 否   | 每页多少对象（默认20） |
| `page_index` | int  | 否   | 第几页（默认1）        |

**响应参数：**

| 参数名      | 类型   | 描述         |
| ----------- | ------ | ------------ |
| `status`    | int    | 状态码       |
| `message`   | string | 返回信息     |
| `user_num`  | int    | 总用户数     |
| `user_list` | array  | 用户对象数组 |

若获取成功，则`user_list`内容如下：

| 参数名       | 类型   | 描述         |
| ------------ | ------ | ------------ |
| `user_id`    | int    | 用户ID       |
| `user_name`  | string | 用户名       |
| `email`      | string | 邮箱         |
| `master`     | bool   | 是否是管理员 |
| `block`      | bool   | 是否被封禁   |
| `campus`     | string | 校区信息     |
| `last_login` | string | 最后登录时间 |

**状态码说明：**

- **200 OK**: 获取成功
- **403 Forbidden**: 无查看权限
- **500 Internal Server Error**: 服务器内部错误

---

### 权限逻辑说明表（暂定）

| 操作              | 允许角色                 | 限制条件                                |
| ----------------- | ------------------------ | --------------------------------------- |
| 提升管理员        | `super_master`           | 不能提升其他super_master                |
| 撤销管理员        | `super_master`           | 只能撤销master用户                      |
| 查看完整用户列表  | `super_master`           | 可查看所有字段                          |
| 查看基础用户列表  | `master`,`super_master ` | 仅可见非管理员用户的非敏感字段          |
| 封禁/解封基础用户 | `master`,`super_master`  | 记得之后搞一个封禁列表的api，调试方便点 |
| 封禁/解封管理员   | `super_master  `         |                                         |

---



