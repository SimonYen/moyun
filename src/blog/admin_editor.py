"""原生文章编辑页：VDitor 所见即所得 + 标准表单保存，绕开 LiveView 状态同步。"""
from urllib.parse import urlencode

from django import forms
from django.shortcuts import redirect, render

from .models import Post, Tag


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['title', 'slug', 'excerpt', 'content', 'tags', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'gf-input'}),
            'slug': forms.TextInput(attrs={'class': 'gf-input'}),
            'excerpt': forms.Textarea(attrs={'class': 'gf-input', 'rows': 3}),
            'content': forms.Textarea(attrs={'class': 'gf-input', 'rows': 16}),
            'tags': forms.CheckboxSelectMultiple(),
            'status': forms.Select(attrs={'class': 'gf-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['slug'].help_text = '留空自动由标题生成'
        self.fields['tags'].queryset = Tag.objects.all()
        self.fields['tags'].required = False


def admin_post_edit(request, object_id=None):
    if not (request.user.is_authenticated and request.user.is_active and request.user.is_staff):
        # 登录后必须回到用户原本要去的页面（写新文章 / 编辑某篇文章），否则会表现为「自动跳回列表」
        return redirect('/admin/login/?' + urlencode({'next': request.get_full_path()}))

    post = None
    if object_id is not None:
        try:
            post = Post.objects.get(pk=object_id)
        except (Post.DoesNotExist, ValueError):
            return redirect('/admin/blog/post/')

    saved = False
    if request.method == 'POST':
        form = PostForm(request.POST, instance=post)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.pk is None:
                obj.author = request.user
            obj.save()
            form.save_m2m()
            if request.POST.get('action') == 'continue':
                return redirect('/admin/blog/post/%d/change/?saved=1' % obj.pk)
            return redirect('/admin/blog/post/')
    else:
        form = PostForm(instance=post)
        saved = request.GET.get('saved') == '1'

    # Rust 模板引擎不能渲染 Django 表单对象，字段在服务端预渲染成 HTML 字符串
    field_names = ['title', 'slug', 'excerpt', 'content', 'tags', 'status']
    fields = []
    for name in field_names:
        bf = form[name]
        fields.append({
            'name': name,
            'label': str(form.fields[name].label or name),
            'required': form.fields[name].required,
            'html_id': bf.id_for_label,
            'html': str(bf),
            'help': str(form.fields[name].help_text or ''),
            'errors': ' '.join(str(e) for e in bf.errors),
            'is_content': name == 'content',
        })

    return render(request, 'djust_admin/post_editor.html', {
        'fields': fields,
        'post_pk': post.pk if post else 0,
        'post_title': post.title if post else '',
        'saved': saved,
        'username': request.user.get_username(),
    })
