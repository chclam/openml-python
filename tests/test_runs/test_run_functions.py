import sys

from sklearn.dummy import DummyClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression, SGDClassifier, LinearRegression
from sklearn.ensemble import RandomForestClassifier, BaggingClassifier
from sklearn.svm import SVC
from sklearn.model_selection import RandomizedSearchCV, GridSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline
import openml
import openml.exceptions
from openml.testing import TestBase

if sys.version_info[0] >= 3:
    from unittest import mock
else:
    import mock


class TestRun(TestBase):

    def _perform_run(self, task_id, num_instances, clf):
        task = openml.tasks.get_task(task_id)
        run = openml.runs.run_task(task, clf)
        run_ = run.publish()
        self.assertEqual(run_, run)
        self.assertIsInstance(run.dataset_id, int)

        # check arff output
        self.assertEqual(len(run.data_content), num_instances)
        return run

    def test_run_regression_on_classif_task(self):
        task_id = 10107

        clf = LinearRegression()
        task = openml.tasks.get_task(task_id)
        self.assertRaises(AttributeError, openml.runs.run_task, task=task, model=clf)

    @mock.patch('openml.flows.sklearn_to_flow')
    def test_check_erronous_sklearn_flow_fails(self, sklearn_to_flow_mock):
        task_id = 10107
        task = openml.tasks.get_task(task_id)

        # Invalid parameter values
        clf = LogisticRegression(C='abc')
        self.assertEqual(sklearn_to_flow_mock.call_count, 0)
        self.assertRaisesRegexp(ValueError, "Penalty term must be positive; got \(C='abc'\)",
                                openml.runs.run_task, task=task, model=clf)

    def test_run_iris(self):
        task_id = 10107
        num_instances = 150

        clf = LogisticRegression()
        self._perform_run(task_id,num_instances, clf)

    def test_run_optimize_randomforest_iris(self):
        task_id = 10107
        num_instances = 150
        num_folds = 10
        num_iterations = 5

        clf = RandomForestClassifier(n_estimators=5)
        param_dist = {"max_depth": [3, None],
                      "max_features": [1,2,3,4],
                      "min_samples_split": [2,3,4,5,6,7,8,9,10],
                      "min_samples_leaf": [1,2,3,4,5,6,7,8,9,10],
                      "bootstrap": [True, False],
                      "criterion": ["gini", "entropy"]}
        cv = StratifiedKFold(n_splits=3)
        random_search = RandomizedSearchCV(clf, param_dist, cv=cv,
                                           n_iter=num_iterations)

        run = self._perform_run(task_id, num_instances, random_search)
        self.assertEqual(len(run.trace_content), num_iterations * num_folds)

    def test_run_optimize_bagging_iris(self):
        task_id = 10107
        num_instances = 150
        num_folds = 10
        num_iterations = 9 # (num values for C times gamma)

        bag = BaggingClassifier(base_estimator=SVC())
        param_dist = {"base_estimator__C": [0.01, 0.1, 10],
                      "base_estimator__gamma": [0.01, 0.1, 10]}
        grid_search = GridSearchCV(bag, param_dist)

        run = self._perform_run(task_id, num_instances, grid_search)
        self.assertEqual(len(run.trace_content), num_iterations * num_folds)

    def test_run_pipeline(self):
        task_id = 10107
        num_instances = 150
        num_folds = 10
        num_iterations = 9  # (num values for C times gamma)

        scaler = StandardScaler(with_mean=False)
        dummy = DummyClassifier(strategy='prior')
        model = Pipeline(steps=(('scaler', scaler), ('dummy', dummy)))

        run = self._perform_run(task_id, num_instances, model)
        self.assertEqual(len(run.trace_content), num_iterations * num_folds)

    def test__run_task_get_arffcontent(self):
        task = openml.tasks.get_task(1939)
        class_labels = task.class_labels

        clf = SGDClassifier(loss='hinge', random_state=1)
        self.assertRaisesRegexp(AttributeError,
                                "probability estimates are not available for loss='hinge'",
                                openml.runs.functions._run_task_get_arffcontent,
                                clf, task, class_labels)

        clf = SGDClassifier(loss='log', random_state=1)
        arff_datacontent, arff_tracecontent = openml.runs.functions._run_task_get_arffcontent(
            clf, task, class_labels)
        # predictions
        self.assertIsInstance(arff_datacontent, list)
        # trace. SGD does not produce any
        self.assertIsInstance(arff_tracecontent, type(None))

        # 10 times 10 fold CV of 150 samples
        self.assertEqual(len(arff_datacontent), 1500)
        for arff_line in arff_datacontent:
            self.assertEqual(len(arff_line), 8)
            self.assertGreaterEqual(arff_line[0], 0)
            self.assertLessEqual(arff_line[0], 9)
            self.assertGreaterEqual(arff_line[1], 0)
            self.assertLessEqual(arff_line[1], 9)
            self.assertGreaterEqual(arff_line[2], 0)
            self.assertLessEqual(arff_line[2], 149)
            self.assertAlmostEqual(sum(arff_line[3:6]), 1.0)
            self.assertIn(arff_line[6], ['Iris-setosa', 'Iris-versicolor',
                                         'Iris-virginica'])
            self.assertIn(arff_line[7], ['Iris-setosa', 'Iris-versicolor',
                                         'Iris-virginica'])

    def test_get_run(self):
        run = openml.runs.get_run(473350)
        self.assertEqual(run.dataset_id, 1167)
        self.assertEqual(run.evaluations['f_measure'], 0.624668)
        for i, value in [(0, 0.66233),
                         (1, 0.639286),
                         (2, 0.567143),
                         (3, 0.745833),
                         (4, 0.599638),
                         (5, 0.588801),
                         (6, 0.527976),
                         (7, 0.666365),
                         (8, 0.56759),
                         (9, 0.64621)]:
            self.assertEqual(run.detailed_evaluations['f_measure'][0][i], value)

    def _check_run(self, run):
        self.assertIsInstance(run, dict)
        self.assertEqual(len(run), 5)

    def test_get_runs_list(self):
        runs = openml.runs.list_runs(id=[2])
        self.assertEqual(len(runs), 1)
        for rid in runs:
            self._check_run(runs[rid])

    def test_get_runs_list_by_task(self):
        task_ids = [20]
        runs = openml.runs.list_runs(task=task_ids)
        self.assertGreaterEqual(len(runs), 590)
        for rid in runs:
            self.assertIn(runs[rid]['task_id'], task_ids)
            self._check_run(runs[rid])
        num_runs = len(runs)

        task_ids.append(21)
        runs = openml.runs.list_runs(task=task_ids)
        self.assertGreaterEqual(len(runs), num_runs + 1)
        for rid in runs:
            self.assertIn(runs[rid]['task_id'], task_ids)
            self._check_run(runs[rid])

    def test_get_runs_list_by_uploader(self):
        # 29 is Dominik Kirchhoff - Joaquin and Jan have too many runs right now
        uploader_ids = [29]

        runs = openml.runs.list_runs(uploader=uploader_ids)
        self.assertGreaterEqual(len(runs), 3)
        for rid in runs:
            self.assertIn(runs[rid]['uploader'], uploader_ids)
            self._check_run(runs[rid])
        num_runs = len(runs)

        uploader_ids.append(274)

        runs = openml.runs.list_runs(uploader=uploader_ids)
        self.assertGreaterEqual(len(runs), num_runs + 1)
        for rid in runs:
            self.assertIn(runs[rid]['uploader'], uploader_ids)
            self._check_run(runs[rid])

    def test_get_runs_list_by_flow(self):
        flow_ids = [1154]
        runs = openml.runs.list_runs(flow=flow_ids)
        self.assertGreaterEqual(len(runs), 1)
        for rid in runs:
            self.assertIn(runs[rid]['flow_id'], flow_ids)
            self._check_run(runs[rid])
        num_runs = len(runs)

        flow_ids.append(1069)
        runs = openml.runs.list_runs(flow=flow_ids)
        self.assertGreaterEqual(len(runs), num_runs + 1)
        for rid in runs:
            self.assertIn(runs[rid]['flow_id'], flow_ids)
            self._check_run(runs[rid])

    def test_get_runs_pagination(self):
        uploader_ids = [1]
        size = 10
        max = 100
        for i in range(0, max, size):
            runs = openml.runs.list_runs(offset=i, size=size, uploader=uploader_ids)
            self.assertGreaterEqual(size, len(runs))
            for rid in runs:
                self.assertIn(runs[rid]["uploader"], uploader_ids)

    def test_get_runs_list_by_filters(self):
        ids = [505212, 6100]
        tasks = [2974, 339]
        uploaders_1 = [1, 17]
        uploaders_2 = [29, 274]
        flows = [74, 1718]

        self.assertRaises(openml.exceptions.OpenMLServerError, openml.runs.list_runs)

        runs = openml.runs.list_runs(id=ids)
        self.assertEqual(len(runs), 2)

        runs = openml.runs.list_runs(task=tasks)
        self.assertGreaterEqual(len(runs), 2)

        runs = openml.runs.list_runs(uploader=uploaders_2)
        self.assertGreaterEqual(len(runs), 10)

        runs = openml.runs.list_runs(flow=flows)
        self.assertGreaterEqual(len(runs), 100)

        runs = openml.runs.list_runs(id=ids, task=tasks, uploader=uploaders_1)

    def test_get_runs_list_by_tag(self):
        runs = openml.runs.list_runs(tag='02-11-16_21.46.39')
        self.assertEqual(len(runs), 1)
