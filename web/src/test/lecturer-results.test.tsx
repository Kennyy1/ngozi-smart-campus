import {render,screen} from '@testing-library/react';
import {MemoryRouter,Route,Routes} from 'react-router-dom';
import {describe,expect,it,vi} from 'vitest';
import {lecturerApi} from '../api/lecturer';
import {CourseResultsPage} from '../pages/lecturer';

vi.mock('../api/lecturer',()=>({lecturerApi:{results:vi.fn()}}));

describe('Lecturer results',()=>{
 it('renders official results as readable table rows instead of raw JSON',async()=>{
  vi.mocked(lecturerApi.results).mockResolvedValue({course_offering_id:'offering-1',registered_student_count:1,published_result_count:1,missing_published_result_count:0,results:[{result_id:'result-1',student_id:'student-1',matriculation_number:'NSC/2026/0001',student_name:'Test Student',final_score:'81.50',grade:'A',grade_point:'5.00',passed:true}]});
  const {container}=render(<MemoryRouter initialEntries={['/lecturer/course-offerings/offering-1/results']}><Routes><Route path="/lecturer/course-offerings/:id/results" element={<CourseResultsPage/>}/></Routes></MemoryRouter>);
  expect(await screen.findByRole('table')).toBeInTheDocument();
  expect(screen.getByText('Test Student')).toBeInTheDocument();
  expect(screen.getByText('NSC/2026/0001')).toBeInTheDocument();
  expect(screen.getByText('81.50')).toBeInTheDocument();
  expect(screen.getByText('Passed')).toBeInTheDocument();
  expect(container.querySelector('pre')).not.toBeInTheDocument();
  expect(container).not.toHaveTextContent('"result_id"');
 });
});
