<script setup>
import NavToggle from '../components/NavToggle.vue'

const services = [
  {
    title: 'مشاريع التخرج الهندسية',
    text: 'تنفيذ مشاريع هندسة الحاسوب والكهرباء والميكاترونيكس وعلوم الحاسوب، مع تقرير وعرض تقديمي.',
  },
  {
    title: 'مشاريع Raspberry Pi',
    text: 'أنظمة ذكاء اصطناعي، بث فيديو، تحكم عن بعد، ومشاريع إنترنت الأشياء على Raspberry Pi 4/5.',
  },
  {
    title: 'مشاريع Arduino',
    text: 'روبوتات، أتمتة منزلية، أجهزة استشعار، وأنظمة تحكم ذكية مع التوصيل والبرمجة.',
  },
  {
    title: 'طباعة الستيكرات',
    text: 'تصميم وطباعة ستيكرات بألوان ثابتة للمنتجات والشركات والفعاليات.',
  },
  {
    title: 'استشارات تقنية',
    text: 'جلسة مجانية لاختيار التقنيات المناسبة وتحليل جدوى الفكرة قبل التنفيذ.',
  },
  {
    title: 'تقارير ووثائق تقنية',
    text: 'تقارير بمعايير أكاديمية، مخططات، ورسوم تدفق جاهزة للتسليم والعرض.',
  },
]

const reasons = [
  { title: 'تسليم في الموعد', text: 'جدول زمني واضح وتحديثات دورية طوال فترة التنفيذ.' },
  { title: 'فريق تقني متخصص', text: 'خبرة عملية في البرمجة والإلكترونيات والأنظمة المدمجة.' },
  { title: 'دعم بعد التسليم', text: 'مرافقة مجانية حتى العرض النهائي والتقييم.' },
  { title: 'أسعار مناسبة للطلاب', text: 'عروض واضحة وخيارات دفع مرنة.' },
]

const stats = [
  { value: '+200', label: 'مشروع منجز' },
  { value: '+150', label: 'عميل راضٍ' },
  { value: '98%', label: 'نسبة نجاح المشاريع' },
  { value: '24', label: 'ساعة متوسط الرد' },
]

const tools = ['Python', 'C / C++', 'Arduino', 'Raspberry Pi', 'IoT / MQTT', 'OpenCV', 'WiFi / Bluetooth']
</script>

<template>
  <div class="page">
    <div class="stack">
      <header class="page-head">
        <div class="title-with-nav">
          <NavToggle />
          <h1 class="page-title">عن المبرمج</h1>
        </div>
      </header>

      <section class="about-split">
        <v-card class="app-card">
          <h2 class="card-title">عمار الأصفر</h2>
          <p class="about-lead">صمّم هذا النظام لسحب بصمات أجهزة ZKTeco وحفظها وتصديرها إلى إكسل.</p>
          <p class="about-text">يعمل من خلال SmartStick، وينفّذ المشاريع الهندسية والتقنية من الفكرة حتى التسليم.</p>
        </v-card>

        <v-card class="app-card">
          <h2 class="card-title">SmartStick</h2>
          <p class="about-lead">مشاريع ذكية لمستقبل مشرق.</p>
          <p class="about-text">تحوّل الفكرة إلى مشروع هندسي جاهز للتسليم: برمجة، إلكترونيات، توثيق أكاديمي، وتصميم مطبوع.</p>
          <a class="text-link" href="https://smartstick-iq.com/" target="_blank" rel="noopener noreferrer">smartstick-iq.com</a>
        </v-card>
      </section>

      <section class="about-stats" aria-label="أرقام الشركة">
        <article v-for="item in stats" :key="item.label" class="stat-card">
          <strong class="stat-value num">{{ item.value }}</strong>
          <span class="stat-label">{{ item.label }}</span>
        </article>
      </section>

      <v-card class="app-card">
        <h2 class="card-title">الخدمات</h2>
        <div class="about-services">
          <article v-for="service in services" :key="service.title">
            <h3>{{ service.title }}</h3>
            <p>{{ service.text }}</p>
          </article>
        </div>
      </v-card>

      <section class="about-split">
        <v-card class="app-card">
          <h2 class="card-title">لماذا SmartStick</h2>
          <div class="about-reasons">
            <article v-for="reason in reasons" :key="reason.title">
              <h3>{{ reason.title }}</h3>
              <p>{{ reason.text }}</p>
            </article>
          </div>
        </v-card>

        <v-card class="app-card">
          <h2 class="card-title">كيف يتم العمل</h2>
          <ol class="about-steps">
            <li>
              <strong>تواصل معنا</strong>
              <span>أرسل الفكرة عبر الهاتف أو واتساب.</span>
            </li>
            <li>
              <strong>التحليل والعرض</strong>
              <span>تحديد المتطلبات والتكلفة والجدول الزمني.</span>
            </li>
            <li>
              <strong>التنفيذ</strong>
              <span>تطوير مع تحديثات دورية.</span>
            </li>
            <li>
              <strong>التسليم والدعم</strong>
              <span>استلام المشروع مع التوثيق ودعم بعد التسليم.</span>
            </li>
          </ol>
        </v-card>
      </section>

      <v-card class="app-card">
        <h2 class="card-title">التقنيات</h2>
        <p class="about-tools">
          <span v-for="tool in tools" :key="tool" class="num">{{ tool }}</span>
        </p>
      </v-card>

      <v-card class="app-card">
        <h2 class="card-title">تواصل معنا</h2>
        <p class="about-text">متاحون يومياً من 9 صباحاً حتى 11 مساءً.</p>
        <div class="contact-actions">
          <v-btn color="primary" href="tel:07830200030">
            <span class="num">07830200030</span>
          </v-btn>
          <v-btn variant="outlined" href="https://wa.me/9647830200030" target="_blank" rel="noopener noreferrer">واتساب</v-btn>
          <v-btn variant="text" href="https://store.smartstick-iq.com/" target="_blank" rel="noopener noreferrer">المتجر</v-btn>
          <v-btn variant="text" href="https://www.facebook.com/smartstickiq" target="_blank" rel="noopener noreferrer">فيسبوك</v-btn>
        </div>
      </v-card>
    </div>
  </div>
</template>
