// Category: Logic Errors
// Error: Off-by-one error in loop

#include <iostream>

int main() {
    int arr[10] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9};
    int sum = 0;
    
    for (int i = 1; i <= 10; i++) {  // ERROR: Starts at 1, goes to 10 (should be 0 to 9)
        sum += arr[i];
    }
    
    std::cout << "Sum: " << sum << std::endl;
    
    return 0;
}
